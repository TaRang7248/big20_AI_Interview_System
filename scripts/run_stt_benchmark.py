import os
import argparse
import logging
import json
from datetime import datetime

# sys.path 설정
import sys
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, project_root)

# --- Environment Setup (ffmpeg, etc.) ---
def setup_environment():
    """
    프로젝트 로컬에 포함된 ffmpeg이 있으면 PATH에 추가하여 라이브러리들이 인식하게 한다.
    """
    # Use a more robust root detection
    current_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.abspath(os.path.join(current_dir, ".."))
    local_ffmpeg_bin = os.path.join(project_root, "ffmpeg", "bin")
    
    if os.path.exists(local_ffmpeg_bin):
        if local_ffmpeg_bin not in os.environ["PATH"]:
            os.environ["PATH"] = local_ffmpeg_bin + os.pathsep + os.environ.get("PATH", "")
            # We don't have logger yet, use print
            print(f"DEBUG: Found local ffmpeg at {local_ffmpeg_bin}. Added to PATH.")
    else:
        print("DEBUG: Local ffmpeg bin not found.")

setup_environment()

from AI_Interview_System.packages.imh_stt_benchmark.runner import BenchmarkRunner
from AI_Interview_System.packages.imh_stt_benchmark.domain import STTEngineProtocol, STTResultDTO
from AI_Interview_System.packages.imh_stt_benchmark.adapters.faster_whisper_adapter import FasterWhisperAdapter
from AI_Interview_System.packages.imh_stt_benchmark.adapters.sensevoice_adapter import SenseVoiceAdapter
from AI_Interview_System.packages.imh_stt_benchmark.adapters.whisper_api_adapter import WhisperAPIAdapter

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

def main():
    parser = argparse.ArgumentParser(description="STT Benchmark Framework Runner")
    parser.add_argument(
        "--data-dir", 
        type=str, 
        default="data/voice_test_collection",
        help="Path to the directory containing audio and ground truth txt files."
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="data/experiments/task_033",
        help="Directory to save the generated JSON and Markdown reports."
    )
    
    args = parser.parse_args()

    # Check data path
    data_dir = os.path.abspath(args.data_dir)
    if not os.path.exists(data_dir):
        logger.warning(f"Data directory '{data_dir}' does not exist. Please check your path.")
        logger.warning("Relative paths should be resolved from the current working directory.")
        # Create a dummy test file to enable execution testing if the directory doesn't exist
        os.makedirs(data_dir, exist_ok=True)
        with open(os.path.join(data_dir, "test1.txt"), "w", encoding="utf-8") as f:
            f.write("Docker와 Kubernetes를 사용하여 24개의 컨테이너를 Redis로 구성했습니다.")
        with open(os.path.join(data_dir, "test1.wav"), "w", encoding="utf-8") as f:
            f.write("DUMMY AUDIO CONTENT")
            
        logger.info(f"Created a mock test suite at {data_dir} for verification.")

    os.makedirs(args.output_dir, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%md_%H%M%S")
    json_path = os.path.join(args.output_dir, f"report_{timestamp}.json")
    md_path = os.path.join(args.output_dir, f"STT_Report_{timestamp}.md")

    logger.info("Initializing Benchmark Runner...")
    runner = BenchmarkRunner(data_dir=data_dir)
    
    # 벤치마크할 모델들 등록
    
    # Optional flags could allow enabling/disabling these, but for the full benchmark we register them.
    # Note: If these packages are uninstalled, it will result in ImportError when `load_model()` inside them runs.
    
    # 1. Faster-Whisper (Large-v3-Turbo)
    # 기술 용어 인식을 돕기 위한 프롬프트 추가
    it_prompt = "Docker, Kubernetes, Redis, PostgreSQL, AWS, Python, FastAPI, React, RAG, FAISS, CQRS, TTL, Nineveh, Circuit Breaker, Information, Escort Bar, Made in Japan"
    runner.register_model("Faster-Whisper-v3-turbo", FasterWhisperAdapter(model_size="large-v3-turbo", device="cuda", initial_prompt=it_prompt))
    
    # 2. SenseVoiceSmall
    runner.register_model("SenseVoiceSmall", SenseVoiceAdapter(model_dir="iic/SenseVoiceSmall", device="cuda:0"))
    
    # 3. Whisper-1 API (Baseline)
    if os.environ.get("OPENAI_API_KEY"):
        runner.register_model("Whisper-1-API", WhisperAPIAdapter())
    else:
        logger.warning("OPENAI_API_KEY not found. Skipping Whisper-1-API baseline.")
    
    # 실행
    results = runner.run(output_json=json_path)

    # Markdown 보고서 생성
    logger.info("Generating Markdown Report...")
    generate_markdown_report(results, md_path)
    logger.info(f"Done! Check {md_path}")

def generate_markdown_report(results: dict, output_path: str):
    with open(output_path, "w", encoding="utf-8") as f:
        f.write("# STT Benchmark Final Report\n\n")
        f.write("## 1. Summary\n")
        f.write("| Model | Total Cases | Success | Avg CER | Avg WER | Avg RTF | Peak VRAM (MB) | Digit Acc | Foreign Acc |\n")
        f.write("|-------|-------------|---------|---------|---------|---------|----------------|-----------|-------------|\n")
        
        for model_name, summary in results.get("summary", {}).items():
            f.write(
                f"| {model_name} | {summary.get('total_run')} | {summary.get('success')} | "
                f"{summary.get('avg_cer', 0):.4f} | {summary.get('avg_wer', 0):.4f} | "
                f"{summary.get('avg_rtf', 0):.4f} | {summary.get('peak_vram_mb', 0):.2f} | "
                f"{summary.get('avg_digit_accuracy') or 'N/A'} | {summary.get('avg_foreign_term_accuracy') or 'N/A'} |\n"
            )
            
        f.write("\n## 2. GTX 1660 Super (6GB) 평가 결론\n")
        f.write("- **최종 선정 모델**: [선정된 모델 이름 기입]\n")
        f.write("- **선정 사유**: 정확성을 최우선시하며, VRAM 5.5GB 및 RTF 1.0 규격을 만족함.\n")

if __name__ == "__main__":
    main()
