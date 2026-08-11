"""Orchestrates the full edit pipeline for one video, source -> ready_for_review.

Stages: probe -> transcribe -> silence -> sentence-safe cut -> face-tracked crop
-> highlight/effect pass -> music -> thumbnail -> metadata -> DB update.

Never uploads anything itself — it stops at 'ready_for_review' and the human
approves the upload separately (see app/youtube/upload.py).
"""
from __future__ import annotations

import dataclasses
import logging
import shutil
import subprocess
from pathlib import Path

from app import db
from app.config import OUTPUT_DIR, THUMBNAIL_DIR, WORKING_DIR, settings
from app.models import Highlight, VideoToggles
from app.pipeline import (
    captions as captions_mod,
    cutter,
    crop_render,
    face_tracker,
    highlight_detector,
    music,
    normalize,
    probe,
    protected_moments,
    segment_planner,
    silence,
    transcribe as transcribe_mod,
    transition_sfx,
)
from app.pipeline.instructions import apply_instructions
from app.pipeline.time_map import build_time_mapper
from app.youtube.metadata import generate_metadata

logger = logging.getLogger(__name__)


def _extract_thumbnail(video_path: str, out_path: str, at_s: float) -> str:
    cmd = [
        "ffmpeg", "-y",
        "-ss", f"{at_s:.3f}",
        "-i", video_path,
        "-frames:v", "1",
        "-q:v", "2",
        out_path,
    ]
    subprocess.run(cmd, check=True, capture_output=True)
    return out_path


def process_video(video_id: str) -> None:
    row = db.get_video(video_id)
    if row is None:
        raise ValueError(f"Unknown video_id {video_id}")

    source_path = row["local_source_path"]
    if not source_path or not Path(source_path).exists():
        raise FileNotFoundError(f"Source file missing for {video_id}: {source_path}")

    toggles = VideoToggles.from_dict(row.get("toggles"))
    if row.get("custom_instructions"):
        toggles.custom_instructions = row["custom_instructions"]
        toggles = apply_instructions(toggles, row["custom_instructions"])

    work_dir = WORKING_DIR / video_id
    work_dir.mkdir(parents=True, exist_ok=True)

    db.set_status(video_id, "processing")
    db.log_event(video_id, "pipeline", "Started processing")

    try:
        # 1. Probe
        info = probe.probe_video(source_path)
        db.update_video(video_id, orientation=info.orientation, duration_s=info.duration_s)
        db.log_event(
            video_id, "probe",
            f"{info.orientation} {info.width}x{info.height} {info.duration_s:.1f}s hdr={info.is_hdr}",
        )

        # 1b. HDR -> SDR tonemap, if needed, so every later re-encode works with
        # plain SDR footage instead of silently crushing/washing out HDR colors.
        if info.is_hdr:
            video_source = str(work_dir / "00_sdr.mp4")
            normalize.tonemap_to_sdr(source_path, video_source)
            db.log_event(video_id, "normalize", "Tonemapped HDR source to SDR (bt709)")
        else:
            video_source = source_path

        # 2. Transcribe (source of truth for sentence-safe cut points)
        segments = transcribe_mod.transcribe(source_path)
        db.update_video(video_id, transcript=[dataclasses.asdict(s) for s in segments])
        db.log_event(video_id, "transcribe", f"{len(segments)} segments")

        # 3. Silence detection + 4. sentence-safe cut plan
        if toggles.cut_silence:
            silence_intervals = silence.detect_silence(source_path)
            keep_ranges = segment_planner.build_keep_ranges(segments, silence_intervals, info.duration_s)
        else:
            from app.models import KeepRange

            keep_ranges = [KeepRange(start=0.0, end=info.duration_s, reason="cut_disabled")]

        # When the source runs long, pick whichever sentence-safe ranges contain
        # the most/loudest highlight moments instead of blindly keeping the
        # earliest ones — this is what makes the resulting video the most
        # eventful part of the source rather than just "whatever came first".
        # Long-form videos get a much higher cap (just a safety net, not a
        # target) since the goal there is "keep almost everything good", not
        # "compress into ~60s".
        max_duration = settings.max_long_form_duration_s if toggles.long_form else settings.max_shorts_duration_s
        scene_changes = highlight_detector.detect_scene_changes(source_path)
        if scene_changes:
            db.log_event(video_id, "cut_plan", f"{len(scene_changes)} scene changes detected (extra selection signal)")
        pre_highlights = highlight_detector.to_timestamp_tuples(
            highlight_detector.detect_audio_peaks(source_path)
            + highlight_detector.detect_keyword_highlights(segments)
            + scene_changes
        )
        # Two independent protection sources, merged: an explicit per-video
        # "don't cut this" instruction, and — running on every video
        # unconditionally, no instruction needed — an automatic guess at the
        # video's actual payoff moment and opening greeting. The system
        # should recognize on its own that "the tooth coming out" is the
        # whole point of that video, not rely on someone remembering to
        # type "kaçırma" every time.
        instructed_protected = protected_moments.find_protected_segments(
            toggles.custom_instructions, segments
        )
        auto_protected = protected_moments.find_auto_topic_segments(segments)
        protected_segments = list({id(s): s for s in instructed_protected + auto_protected}.values())
        if instructed_protected:
            db.log_event(
                video_id, "cut_plan",
                f"Protected from cutting per instruction: {[s.text[:40] for s in instructed_protected]}",
            )
        if auto_protected:
            db.log_event(
                video_id, "cut_plan",
                f"Auto-protected as the video's core topic/greeting: {[s.text[:40] for s in auto_protected]}",
            )
        keep_ranges = segment_planner.select_best_ranges(
            keep_ranges, pre_highlights, max_duration,
            protected_timestamps=[s.start for s in protected_segments],
            hook_seconds=settings.hook_guarantee_s if not toggles.long_form else 0.0,
        )
        db.log_event(
            video_id, "cut_plan",
            f"{len(keep_ranges)} ranges, {segment_planner.total_duration(keep_ranges):.1f}s kept",
        )

        # 5. Render the cut — crossfaded transitions between kept ranges where
        # both sides are long enough, hard cuts otherwise (see cutter.py).
        cut_path = str(work_dir / "01_cut.mp4")
        cutter.render_cut(video_source, keep_ranges, cut_path)
        crossfade_s = cutter.XFADE_DURATION_S if cutter.can_crossfade(keep_ranges) else 0.0
        db.log_event(
            video_id, "cut",
            f"Rendered sentence-safe cut ({'crossfade' if crossfade_s else 'hard cut'} transitions)",
        )

        # A synthesized transition "whoosh" on every crossfade cut — audio
        # only (-c:v copy), no extra video re-encode generation. Skipped
        # entirely when there are no crossfades (single range / hard cuts).
        transition_times = cutter.crossfade_transition_times(keep_ranges) if crossfade_s else []
        if transition_times:
            whoosh_path = str(work_dir / "01b_whoosh.mp4")
            transition_sfx.apply_transition_sounds(cut_path, whoosh_path, transition_times)
            cut_path = whoosh_path
            db.log_event(video_id, "cut", f"Added transition whoosh at {len(transition_times)} cut(s)")

        # Remap transcript timestamps into the post-cut timeline for later stages.
        # Only segments that actually survived the (possibly highlight-driven,
        # non-contiguous) range selection are kept — anything that fell in a
        # dropped gap is excluded rather than mapped to a bogus clamped time.
        # crossfade_s must mirror exactly what render_cut just did above, or
        # captions/effects drift out of sync a little more with every transition.
        def _survived(seg) -> bool:
            return any(r.start <= seg.start and seg.end <= r.end for r in keep_ranges)

        time_map = build_time_mapper(keep_ranges, crossfade_s=crossfade_s)
        mapped_segments = [
            type(seg)(
                text=seg.text,
                start=time_map(seg.start),
                end=time_map(seg.end),
                words=[
                    type(w)(word=w.word, start=time_map(w.start), end=time_map(w.end))
                    for w in seg.words
                ],
            )
            for seg in segments
            if _survived(seg)
        ]

        # 6. Face-tracked crop to target aspect
        cut_info = probe.probe_video(cut_path)
        target_w, target_h = cut_info.target_size
        if toggles.face_crop:
            keyframes = face_tracker.build_crop_path(
                cut_path, cut_info.width, cut_info.height, target_w, target_h, cut_info.duration_s
            )
        else:
            keyframes = face_tracker.build_static_crop_keyframes(
                cut_path, cut_info.width, cut_info.height, target_w, target_h, cut_info.duration_s
            )
        cropped_path = str(work_dir / "02_cropped.mp4")
        crop_render.render_crop(cut_path, cropped_path, keyframes, target_w, target_h, work_dir=str(work_dir))
        db.log_event(video_id, "crop", f"face_crop={toggles.face_crop} -> {target_w}x{target_h}")

        # 7. Highlight detection — no visual overlay is ever rendered from
        # this anymore (flash/vignette/color-pop/text-callout were all tried
        # and explicitly rejected as looking AI-made rather than like a
        # professional YouTuber's edit); highlights now exist purely as a
        # signal for music mood selection below.
        current_path = cropped_path
        if toggles.effects:
            highlights = highlight_detector.detect_highlights(cropped_path, mapped_segments)
            protected_texts = {s.text for s in protected_segments}
            for seg in mapped_segments:
                if seg.text in protected_texts:
                    highlights.append(Highlight(t=seg.start, kind="protected", label=seg.text[:24], confidence=0.95))
            highlights.sort(key=lambda h: h.t)
            db.log_event(video_id, "effects", f"{len(highlights)} highlights detected (music-mood signal only)")
        else:
            highlights = []

        # 7b. Word-synced burned-in captions
        if toggles.captions:
            ass_path = str(work_dir / "captions.ass")
            captions_mod.build_ass_captions(mapped_segments, ass_path, target_w, target_h)
            captioned_path = str(work_dir / "03b_captions.mp4")
            captions_mod.burn_captions(current_path, ass_path, captioned_path)
            current_path = captioned_path
            db.log_event(video_id, "captions", "Burned in word-synced captions")

        # 8. Music
        if toggles.music:
            with_music_path = str(work_dir / "04_music.mp4")
            current_path, track = music.apply_music_if_available(
                current_path, with_music_path, mapped_segments, highlights,
                mood_override=toggles.music_mood,
            )
            db.log_event(video_id, "music", track.mood if track else "no track available")
        else:
            track = None

        # 9. Finalize output — archive whatever was there before (a
        # reprocess) so earlier edits stay reachable instead of being
        # silently overwritten.
        archived_version = db.archive_current_version(video_id)
        if archived_version is not None:
            db.log_event(video_id, "pipeline", f"Archived previous edit as V{archived_version}")

        output_path = str(OUTPUT_DIR / f"{video_id}.mp4")
        shutil.copyfile(current_path, output_path)

        # 10. Thumbnail
        thumb_path = str(THUMBNAIL_DIR / f"{video_id}.jpg")
        final_info = probe.probe_video(output_path)
        _extract_thumbnail(output_path, thumb_path, at_s=min(1.0, final_info.duration_s / 2))

        # 11. Metadata
        made_for_kids = (
            toggles.made_for_kids if toggles.made_for_kids is not None else settings.made_for_kids_default
        )
        meta = generate_metadata(mapped_segments, track.mood if track else None, long_form=toggles.long_form)

        db.update_video(
            video_id,
            output_path=output_path,
            thumbnail_path=thumb_path,
            title=meta.title,
            description=meta.description,
            tags=meta.tags,
            made_for_kids=made_for_kids,
        )
        db.set_status(video_id, "ready_for_review")
        db.log_event(video_id, "pipeline", "Ready for review")

        from app.jobs.notify import notify_ready_for_review

        notify_ready_for_review(video_id, meta.title)

    except Exception as exc:  # noqa: BLE001
        logger.exception("Pipeline failed for %s", video_id)
        db.set_status(video_id, "failed", error=str(exc))
        db.log_event(video_id, "pipeline", f"FAILED: {exc}")
        raise
