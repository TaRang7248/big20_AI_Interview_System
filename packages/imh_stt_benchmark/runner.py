import os
import json
import logging
from typing import List, Dict, Any, Type
from .domain import STTEngineProtocol, TestCase
from .evaluator import STTEvaluator

logger = logging.getLogger(__name__)

class BenchmarkRunner:
    """
    지정된 데이터 디렉토리를 순회하며 테스트 케이스를 수집하고,
    등록된 모델들에 대해 전면 평가를 수행한 뒤 병합 리포트를 생성한다.
    """
    def __init__(self, data_dir: str):
        self.data_dir = data_dir
        self.models: Dict[str, STTEngineProtocol] = {}

    def register_model(self, name: str, engine: STTEngineProtocol):
        self.models[name] = engine

    def _collect_test_cases(self) -> List[TestCase]:
        """
        데이터 디렉토리를 재귀탐색하여 오디오 파일과 ground truth 텍스트 짝을 찾는다.
        디렉토리 내에 transcriptions.json 파일이 있으면 우선 참조하고, 없으면 동일 이름의 .txt 파일을 매칭한다.
        """
        cases = []
        if not os.path.exists(self.data_dir):
            logger.warning(f"Data directory not found: {self.data_dir}")
            return cases
            
        transcriptions_path = os.path.join(self.data_dir, "transcriptions.json")
        transcriptions_map = {}
        if os.path.exists(transcriptions_path):
            with open(transcriptions_path, "r", encoding="utf-8") as f:
                transcriptions_map = json.load(f)

        for root, dirs, files in os.walk(self.data_dir):
            for file in files:
                ext = os.path.splitext(file)[1].lower()
                if ext in [".wav", ".flac", ".mp3"]:
                    base_name = os.path.splitext(file)[0]
                    audio_path = os.path.join(root, file)
                    
                    gt_text = ""
                    if file in transcriptions_map:
                        gt_text = transcriptions_map[file]
                    elif os.path.exists(os.path.join(root, base_name + ".txt")):
                        with open(os.path.join(root, base_name + ".txt"), "r", encoding="utf-8") as f:
                            gt_text = f.read().strip()
                    else:
                        logger.warning(f"Ground truth not found for {audio_path}. Skipping.")
                        continue
                        
                    cases.append(TestCase(audio_path=audio_path, ground_truth=gt_text))
        return cases

    def run(self, output_json: str = "benchmark_report.json") -> Dict[str, Any]:
        cases = self._collect_test_cases()
        logger.info(f"Found {len(cases)} test cases in {self.data_dir}")
        
        report = {
            "summary": {},
            "results": {}
        }
        
        for model_name, engine in self.models.items():
            logger.info(f"--- Running benchmark for: {model_name} ---")
            try:
                evaluator = STTEvaluator(engine=engine, max_vram_mb=5500.0)
                
                model_results = []
                for i, case in enumerate(cases):
                    msg = f"[{model_name}] Evaluating {i+1}/{len(cases)}: {os.path.basename(case.audio_path)}..."
                    logger.info(msg)
                    print(msg, flush=True)
                    res = evaluator.evaluate(case)
                    model_results.append(res)
                    
                    status_msg = f"  >> Status: {res['status']}, RTF: {res.get('rtf', 0):.4f}"
                    logger.info(status_msg)
                    print(status_msg, flush=True)
                    
                report["results"][model_name] = model_results
                
                # 애그리게이션 로직 (SUCCESS 케이스 평균)
                success_cases = [r for r in model_results if r["status"] == "SUCCESS"]
                if success_cases:
                    avg_wer = sum(r["metrics"]["wer"] for r in success_cases) / len(success_cases)
                    avg_cer = sum(r["metrics"]["cer"] for r in success_cases) / len(success_cases)
                    avg_rtf = sum(r["rtf"] for r in success_cases) / len(success_cases)
                    max_vram = max(r["peak_vram_mb"] for r in success_cases)
                    
                    da = [r["metrics"]["digit_accuracy"] for r in success_cases if r["metrics"]["digit_accuracy"] is not None]
                    avg_da = sum(da) / len(da) if da else None
                    
                    fa = [r["metrics"]["foreign_term_accuracy"] for r in success_cases if r["metrics"]["foreign_term_accuracy"] is not None]
                    avg_fa = sum(fa) / len(fa) if fa else None
                    
                    report["summary"][model_name] = {
                        "total_run": len(model_results),
                        "success": len(success_cases),
                        "avg_wer": avg_wer,
                        "avg_cer": avg_cer,
                        "avg_rtf": avg_rtf,
                        "peak_vram_mb": max_vram,
                        "avg_digit_accuracy": avg_da,
                        "avg_foreign_term_accuracy": avg_fa
                    }
                else:
                    report["summary"][model_name] = {
                        "total_run": len(model_results),
                        "success": 0
                    }
            except Exception as e:
                logger.error(f"Critical error during benchmark for {model_name}: {e}")
                report["summary"][model_name] = {"error": str(e), "status": "FAILED"}
            finally:
                logger.info(f"Unloading model {model_name} to free up VRAM...")
                if hasattr(engine, 'unload') and callable(getattr(engine, 'unload')):
                    try:
                        engine.unload()
                    except Exception as unload_e:
                        logger.warning(f"Failed to unload {model_name}: {unload_e}")
        
        with open(output_json, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=4, ensure_ascii=False)
            
        logger.info(f"Benchmark finished. Report saved to {output_json}")
        return report
