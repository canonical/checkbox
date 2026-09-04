#!/usr/bin/env python3
import argparse
import logging
import os
import shlex
import subprocess
from dataclasses import dataclass


logging.basicConfig(
    level=logging.INFO,
    format="[%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(),
    ],
)


@dataclass(frozen=True)
class PipelineCase:
    runtime: str
    scenario: str
    output_name: str
    pipeline_template: str
    model_name: str
    labels_name: str
    settings_name: str = ""


PIPELINE_CASES = {
    ("litert", "image-classification"): PipelineCase(
        runtime="litert",
        scenario="image-classification",
        output_name="image-classification-LiteRT.mp4",
        model_name="inception_v3_quantized.tflite",
        labels_name="classification.json",
        pipeline_template=(
            "filesrc location={video} ! qtdemux ! queue ! h264parse ! "
            "v4l2h264dec capture-io-mode=4 output-io-mode=4 ! "
            "video/x-raw,format=NV12 ! videoscale ! {processing_caps} ! "
            "queue ! tee name=split split. ! queue ! "
            'qtivcomposer name=mixer sink_1::position="<30, 30>" '
            'sink_1::dimensions="<640, 360>" ! '
            "queue ! video/x-raw,format=NV12,"
            "width={processing_width},height={processing_height},"
            "interlace-mode=progressive,colorimetry=bt601 ! "
            "v4l2h264enc capture-io-mode=4 output-io-mode=5 ! "
            "h264parse ! queue ! "
            "mp4mux ! queue ! filesink location={output} split. ! queue ! "
            "qtimlvconverter ! queue ! qtimltflite delegate=external "
            "external-delegate-path=libQnnTFLiteDelegate.so "
            'external-delegate-options="QNNExternalDelegate,'
            'backend_type=htp;" '
            "model={model} ! queue ! qtimlpostprocess "
            "settings='{{\"confidence\": 40.0}}' "
            "results=2 module=mobilenet labels={labels} ! "
            "video/x-raw,format=BGRA,width=640,height=360 ! queue ! mixer."
        ),
    ),
    ("litert", "object-detection"): PipelineCase(
        runtime="litert",
        scenario="object-detection",
        output_name="object-detection-LiteRT.mp4",
        model_name="yolox_quantized.tflite",
        labels_name="yolox.json",
        pipeline_template=(
            "filesrc location={video} ! qtdemux ! queue ! h264parse ! "
            "v4l2h264dec capture-io-mode=4 output-io-mode=4 ! "
            "video/x-raw,format=NV12 ! videoscale ! {processing_caps} ! "
            "queue ! tee name=split split. ! queue ! "
            "qtivcomposer name=mixer ! queue ! "
            "video/x-raw,format=NV12,"
            "width={processing_width},height={processing_height},"
            "interlace-mode=progressive,colorimetry=bt601 ! "
            "v4l2h264enc capture-io-mode=4 output-io-mode=5 ! "
            "h264parse ! queue ! "
            "mp4mux ! queue ! filesink location={output} split. ! "
            "queue ! qtimlvconverter ! queue ! "
            "qtimltflite delegate=external "
            "external-delegate-path=libQnnTFLiteDelegate.so "
            'external-delegate-options="QNNExternalDelegate,'
            'backend_type=htp;" model={model} ! queue ! '
            "qtimlpostprocess settings='{{\"confidence\": 75.0}}' "
            "results=10 module=yolov8 labels={labels} ! "
            "video/x-raw,format=BGRA,width=640,height=360 ! queue ! mixer."
        ),
    ),
    ("litert", "image-segmentation"): PipelineCase(
        runtime="litert",
        scenario="image-segmentation",
        output_name="image-segmentation-LiteRT.mp4",
        model_name="deeplabv3_plus_mobilenet_quantized.tflite",
        labels_name="deeplabv3_resnet50.json",
        pipeline_template=(
            "filesrc location={video} ! qtdemux ! queue ! h264parse ! "
            "v4l2h264dec capture-io-mode=4 output-io-mode=4 ! "
            "video/x-raw,format=NV12 ! videoscale ! {processing_caps} ! "
            "queue ! tee name=split split. ! queue ! "
            "qtivcomposer name=mixer "
            'sink_1::dimensions="<{processing_width},{processing_height}>" '
            "sink_1::alpha=0.5 ! queue ! "
            "video/x-raw,format=NV12,"
            "width={processing_width},height={processing_height},"
            "interlace-mode=progressive,colorimetry=bt601 ! "
            "v4l2h264enc capture-io-mode=4 output-io-mode=5 ! "
            "h264parse ! queue ! "
            "mp4mux ! queue ! filesink location={output} split. ! "
            "queue ! qtimlvconverter ! queue ! "
            "qtimltflite delegate=external "
            "external-delegate-path=libQnnTFLiteDelegate.so "
            'external-delegate-options="QNNExternalDelegate,'
            'backend_type=htp;" model={model} ! queue ! '
            "qtimlpostprocess module=deeplab-argmax labels={labels} ! "
            "video/x-raw,width=256,height=144 ! queue ! mixer."
        ),
    ),
    ("litert", "pose-detection"): PipelineCase(
        runtime="litert",
        scenario="pose-detection",
        output_name="pose-detection-LiteRT.mp4",
        model_name="hrnet_pose_quantized.tflite",
        labels_name="hrnet_pose.json",
        settings_name="hrnet_settings.json",
        pipeline_template=(
            "filesrc location={video} ! qtdemux ! queue ! h264parse ! "
            "v4l2h264dec capture-io-mode=4 output-io-mode=4 ! "
            "video/x-raw,format=NV12 ! videoscale ! {processing_caps} ! "
            "queue ! tee name=split split. ! queue ! "
            "qtivcomposer name=mixer "
            'sink_1::dimensions="<{processing_width},{processing_height}>" '
            "! queue ! "
            "video/x-raw,format=NV12,"
            "width={processing_width},height={processing_height},"
            "interlace-mode=progressive,colorimetry=bt601 ! "
            "v4l2h264enc capture-io-mode=4 output-io-mode=5 ! "
            "h264parse ! queue ! "
            "mp4mux ! queue ! filesink location={output} split. ! "
            "queue ! qtimlvconverter ! queue ! "
            "qtimltflite delegate=external "
            "external-delegate-path=libQnnTFLiteDelegate.so "
            'external-delegate-options="QNNExternalDelegate,'
            'backend_type=htp;" model={model} ! queue ! '
            "qtimlpostprocess results=2 module=hrnet labels={labels} "
            "settings={settings} ! "
            "video/x-raw,format=BGRA,width=640,height=360 ! queue ! mixer."
        ),
    ),
    ("snpe", "image-classification"): PipelineCase(
        runtime="snpe",
        scenario="image-classification",
        output_name="image-classification-SNPE.mp4",
        model_name="inceptionv3.dlc",
        labels_name="classification.json",
        pipeline_template=(
            "filesrc location={video} ! qtdemux ! queue ! h264parse ! "
            "v4l2h264dec capture-io-mode=4 output-io-mode=4 ! "
            "video/x-raw,format=NV12 ! videoscale ! {processing_caps} ! "
            "queue ! tee name=split split. ! queue ! "
            'qtivcomposer name=mixer sink_1::position="<30, 30>" '
            'sink_1::dimensions="<640, 360>" ! queue ! '
            "video/x-raw,format=NV12,"
            "width={processing_width},height={processing_height},"
            "interlace-mode=progressive,colorimetry=bt601 ! "
            "v4l2h264enc capture-io-mode=4 output-io-mode=5 ! "
            "h264parse ! queue ! "
            "mp4mux ! queue ! filesink location={output} split. ! "
            "queue ! qtimlvconverter ! queue ! "
            "qtimlsnpe delegate=dsp model={model} ! queue ! "
            "qtimlpostprocess settings='{{\"confidence\": 40.0}}' "
            "results=2 module=mobilenet-softmax labels={labels} ! "
            "video/x-raw,format=BGRA,width=640,height=360 ! queue ! mixer."
        ),
    ),
    ("snpe", "object-detection"): PipelineCase(
        runtime="snpe",
        scenario="object-detection",
        output_name="object-detection-SNPE.mp4",
        model_name="yolox.dlc",
        labels_name="yolox.json",
        pipeline_template=(
            "filesrc location={video} ! qtdemux ! queue ! h264parse ! "
            "v4l2h264dec capture-io-mode=4 output-io-mode=4 ! "
            "video/x-raw,format=NV12 ! videoscale ! {processing_caps} ! "
            "queue ! tee name=split split. ! queue ! "
            "qtivcomposer name=mixer ! queue ! "
            "video/x-raw,format=NV12,"
            "width={processing_width},height={processing_height},"
            "interlace-mode=progressive,colorimetry=bt601 ! "
            "v4l2h264enc capture-io-mode=4 output-io-mode=5 ! "
            "h264parse ! queue ! "
            "mp4mux ! queue ! filesink location={output} split. ! "
            "queue ! qtimlvconverter ! queue ! "
            "qtimlsnpe delegate=dsp model={model} "
            'tensors="<boxes,scores,class_idx>" ! queue ! '
            'qtimlpostprocess settings="{{\\"confidence\\": 70.0}}" '
            "results=5 module=yolov8 labels={labels} ! "
            "video/x-raw,width=640,height=360 ! queue ! mixer."
        ),
    ),
    ("snpe", "image-segmentation"): PipelineCase(
        runtime="snpe",
        scenario="image-segmentation",
        output_name="image-segmentation-SNPE.mp4",
        model_name="deeplabv3_plus_mobilenet.dlc",
        labels_name="deeplabv3_resnet50.json",
        pipeline_template=(
            "filesrc location={video} ! qtdemux ! queue ! h264parse ! "
            "v4l2h264dec capture-io-mode=4 output-io-mode=4 ! "
            "video/x-raw,format=NV12 ! videoscale ! {processing_caps} ! "
            "queue ! tee name=split split. ! queue ! "
            "qtivcomposer name=mixer "
            'sink_1::dimensions="<{processing_width},{processing_height}>" '
            "sink_1::alpha=0.5 ! queue ! "
            "v4l2h264enc capture-io-mode=4 output-io-mode=5 ! "
            "h264parse ! queue ! "
            "mp4mux ! queue ! filesink location={output} split. ! "
            "queue ! qtimlvconverter ! queue ! "
            "qtimlsnpe delegate=dsp model={model} ! queue ! "
            "qtimlpostprocess module=deeplab-argmax labels={labels} ! "
            "video/x-raw,width=640,height=360 ! queue ! mixer."
        ),
    ),
}


def detect_platform_profile():
    """Best-effort platform profile detection for path/env defaults."""
    # SNAP is always present in Ubuntu Core and often absent on classic.
    if os.environ.get("SNAP"):
        return "core"

    os_release = "/etc/os-release"
    if not os.path.exists(os_release):
        return "classic"

    data = {}
    with open(os_release, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if "=" not in line or line.startswith("#"):
                continue
            key, value = line.split("=", 1)
            data[key] = value.strip('"')

    if data.get("ID") == "ubuntu-core" or "ubuntu-core" in data.get(
        "ID_LIKE", ""
    ):
        return "core"
    return "classic"


def resolve_artifact_path(
    artifact_name,
    default_file_name,
    explicit_path,
    explicit_dir,
    default_dir,
    required=True,
    allow_dir_option=True,
):
    if explicit_path:
        return explicit_path

    base_dir = explicit_dir or default_dir
    if base_dir:
        return os.path.join(base_dir, default_file_name)

    if required:
        if allow_dir_option:
            logging.error(
                "Missing %s path. Use --%s-path or --%s-dir "
                "(or set --test-data-dir/QIM_TEST_DATA_DIR "
                "for defaults).",
                artifact_name,
                artifact_name,
                artifact_name,
            )
        else:
            logging.error(
                "Missing %s path. Use --%s-path "
                "(or set --test-data-dir/QIM_TEST_DATA_DIR "
                "for defaults).",
                artifact_name,
                artifact_name,
            )
    return ""


def build_case_context(
    video_path, output_path, model_path, labels_path, settings_path
):
    context = {
        "video": video_path,
        "output": output_path,
        "model": model_path,
        "labels": labels_path,
        "processing_caps": (
            "video/x-raw,format=NV12,width={width},height={height},"
            "pixel-aspect-ratio=1/1"
        ).format(
            width=1920,
            height=1080,
        ),
        "settings": settings_path,
    }
    return context


def run_pipeline(args):
    case_key = (args.runtime, args.scenario)
    if case_key not in PIPELINE_CASES:
        logging.error(
            "Unsupported scenario/runtime combination: %s/%s",
            args.scenario,
            args.runtime,
        )
        return 2

    case = PIPELINE_CASES[case_key]
    profile = (
        args.profile if args.profile != "auto" else detect_platform_profile()
    )

    qim_test_data_dir = os.environ.get("QIM_TEST_DATA_DIR", "")
    test_video_file = os.environ.get("TEST_VIDEO_FILE", "")
    # Backward-compatible fallbacks for older jobs.
    test_data_dir = os.environ.get("TEST_DATA_DIR", "")
    test_models_dir = os.environ.get("TEST_MODELS_DIR", "")
    test_settings_dir = os.environ.get("TEST_SETTINGS_DIR", "")
    test_labels_dir = os.environ.get("TEST_LABELS_DIR", "")

    default_data_dir = ""
    if args.test_data_dir:
        default_data_dir = args.test_data_dir
    elif qim_test_data_dir:
        default_data_dir = qim_test_data_dir
    elif test_data_dir:
        default_data_dir = test_data_dir

    default_models_dir = default_data_dir or test_models_dir
    default_labels_dir = default_data_dir or test_labels_dir
    default_settings_dir = default_data_dir or test_settings_dir
    default_video_dir = default_data_dir

    explicit_video_path = args.video_path or test_video_file

    video_path = resolve_artifact_path(
        "video",
        "test_video.mp4",
        explicit_video_path,
        args.video_dir,
        default_video_dir,
    )
    model_path = resolve_artifact_path(
        "model",
        case.model_name,
        args.model_path,
        "",
        default_models_dir,
        allow_dir_option=False,
    )
    labels_path = resolve_artifact_path(
        "labels",
        case.labels_name,
        args.labels_path,
        "",
        default_labels_dir,
        allow_dir_option=False,
    )
    settings_path = ""
    if case.settings_name:
        settings_path = resolve_artifact_path(
            "settings",
            case.settings_name,
            args.settings_path,
            "",
            default_settings_dir,
            allow_dir_option=False,
        )

    if not video_path or not model_path or not labels_path:
        return 2
    if case.settings_name and not settings_path:
        return 2

    if args.output_path:
        output_path = args.output_path
    else:
        session_share_root = os.environ.get("PLAINBOX_SESSION_SHARE", "")
        if args.output_dir:
            session_share_qim = args.output_dir
        elif session_share_root:
            session_share_qim = os.path.join(session_share_root, "qim")
        else:
            logging.error(
                "Output path is missing. Use --output-path/--output-dir "
                "or set PLAINBOX_SESSION_SHARE."
            )
            return 2
        output_path = os.path.join(session_share_qim, case.output_name)

    output_parent = os.path.dirname(output_path)
    if output_parent:
        os.makedirs(output_parent, exist_ok=True)

    context = build_case_context(
        video_path,
        output_path,
        model_path,
        labels_path,
        settings_path,
    )
    context["processing_caps"] = (
        "video/x-raw,format=NV12,width={width},height={height},"
        "pixel-aspect-ratio=1/1"
    ).format(
        width=args.processing_width,
        height=args.processing_height,
    )
    context["processing_width"] = args.processing_width
    context["processing_height"] = args.processing_height

    if not args.dry_run:
        required_paths = [video_path, model_path, labels_path]
        if settings_path:
            required_paths.append(settings_path)
        for path in required_paths:
            if not os.path.exists(path):
                logging.error("Required input file does not exist: %s", path)
                return 2

    pipeline = case.pipeline_template.format(**context)
    gst_cmd = ["gst-launch-1.0", "-f", "-v"] + shlex.split(pipeline)
    cmd = [
        "timeout",
        "-k",
        "5s",
        "{}s".format(args.timeout),
    ] + gst_cmd

    env = os.environ.copy()
    env["GST_DEBUG"] = str(args.gst_debug)

    # USER_DEFINED_GST_PLUGIN_PATH must be set so QIM plugins are found
    # regardless of whether we run directly or inside a Checkbox snap
    #  (where SNAP is always set, making detect_platform_profile()
    #   return 'core' even on classic).
    gst_ld_path = os.environ.get("USER_DEFINED_GST_LD_LIBRARY_PATH")
    gst_plugin_path = os.environ.get("USER_DEFINED_GST_PLUGIN_PATH")
    logging.info("User defined LD_LIBRARY_PATH: %s", gst_ld_path)
    logging.info("User defined GST_PLUGIN_PATH: %s", gst_plugin_path)
    if gst_ld_path:
        logging.info("Append %s to LD_LIBRARY_PATH for GStreamer", gst_ld_path)
        env.update(LD_LIBRARY_PATH=gst_ld_path)
    if gst_plugin_path:
        logging.info(
            "Append %s to GST_PLUGIN_PATH for GStreamer",
            gst_plugin_path,
        )
        env.update(GST_PLUGIN_PATH=gst_plugin_path)

    logging.info(
        "Running QIM AI/ML pipeline: scenario=%s runtime=%s profile=%s",
        args.scenario,
        args.runtime,
        profile,
    )
    logging.info("Resolved gst-launch command:\n%s", shlex.join(gst_cmd))

    if args.dry_run:
        logging.info("Dry-run command:\n%s", shlex.join(cmd))
        return 0

    result = subprocess.run(cmd, env=env)
    if result.returncode != 0:
        logging.error("Pipeline failed with return code %s", result.returncode)
        return result.returncode

    logging.info("Pipeline completed: %s", context["output"])
    return 0


def main():
    parser = argparse.ArgumentParser(
        description="Run QIM AI/ML gstreamer pipelines used by Checkbox jobs.",
    )
    subparsers = parser.add_subparsers(dest="subcommand", required=True)

    run_parser = subparsers.add_parser("run", help="Run a pipeline case")
    run_parser.add_argument(
        "--runtime",
        required=True,
        choices=["litert", "snpe"],
        help="Runtime backend for inference",
    )
    run_parser.add_argument(
        "--scenario",
        required=True,
        choices=[
            "image-classification",
            "object-detection",
            "image-segmentation",
            "pose-detection",
        ],
        help="AI/ML scenario",
    )
    run_parser.add_argument(
        "--profile",
        default="auto",
        choices=["auto", "classic", "core"],
        help="Platform profile controlling environment defaults",
    )
    run_parser.add_argument(
        "--timeout",
        default=60,
        type=int,
        help="Pipeline timeout in seconds",
    )
    run_parser.add_argument(
        "--gst-debug",
        default=2,
        type=int,
        help="GST_DEBUG value",
    )
    run_parser.add_argument(
        "--processing-width",
        default=1920,
        type=int,
        help="Normalize decoded source to this width before tee/mixer",
    )
    run_parser.add_argument(
        "--processing-height",
        default=1080,
        type=int,
        help="Normalize decoded source to this height before tee/mixer",
    )
    run_parser.add_argument(
        "--test-data-dir",
        default="",
        help=(
            "Default base directory for model/label/settings when "
            "specific paths are not provided"
        ),
    )
    run_parser.add_argument(
        "--video-path",
        default="",
        help=("Full path to input video file " "(fallback: TEST_VIDEO_FILE)"),
    )
    run_parser.add_argument(
        "--model-path",
        default="",
        help="Full path to model file",
    )
    run_parser.add_argument(
        "--labels-path",
        default="",
        help="Full path to labels file",
    )
    run_parser.add_argument(
        "--settings-path",
        default="",
        help="Full path to optional settings file (used by pose-detection)",
    )
    run_parser.add_argument(
        "--video-dir",
        default="",
        help="Directory for input video when --video-path is not used",
    )
    run_parser.add_argument(
        "--output-dir",
        default="",
        help="Path to session output directory",
    )
    run_parser.add_argument(
        "--output-path",
        default="",
        help=(
            "Full output video path "
            "(overrides --output-dir default filename)"
        ),
    )
    run_parser.add_argument(
        "--gst-plugin-path",
        default="",
        help=(
            "Override GST_PLUGIN_PATH (default: "
            "/usr/lib/aarch64-linux-gnu/gstreamer-1.0/ "
            "when not set in environment)"
        ),
    )
    run_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print resolved command only",
    )

    args = parser.parse_args()
    if args.subcommand == "run":
        if args.processing_width <= 0 or args.processing_height <= 0:
            logging.error(
                "--processing-width and --processing-height must be > 0"
            )
            return 2
    if args.subcommand == "run":
        return run_pipeline(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
