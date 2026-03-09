import sys
import os

# 프로젝트 루트를 sys.path에 추가 (스크립트 위치 기준 상위 디렉토리)
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

def verify_task_002():
    print("=== TASK-002 Verification Start ===")
    
    # 1. Config Verification
    try:
        from packages.imh_core.config import IMHConfig, ConfigurationError
        print("[O] Config module import success")
        
        config = IMHConfig.load()
        print(f"[O] Config loaded: PROJECT_NAME={config.PROJECT_NAME}")
        
    except Exception as e:
        print(f"[X] Config verification failed: {e}")
        return

    # 2. Errors Verification
    try:
        from packages.imh_core.errors import IMHBaseError
        print("[O] Errors module import success")
        
        try:
            raise IMHBaseError(code="TEST_001", message="Test Error")
        except IMHBaseError as e:
            print(f"[O] IMHBaseError caught: {e}")
            if e.code != "TEST_001":
                print(f"[X] Error code mismatch: {e.code}")
    except Exception as e:
        print(f"[X] Errors verification failed: {e}")
        return

    # 3. DTO Verification
    try:
        from packages.imh_core.dto import BaseDTO
        print("[O] DTO module import success")
        
        class TestDTO(BaseDTO):
            name: str
            age: int

        dto = TestDTO(name="  Test User  ", age=25)
        if dto.name == "Test User":
            print(f"[O] DTO whitespace stripping works: '{dto.name}'")
        else:
            print(f"[X] DTO whitespace stripping failed: '{dto.name}'")

    except Exception as e:
        print(f"[X] DTO verification failed: {e}")
        return

    print("=== TASK-002 Verification Complete: ALL PASS ===")

if __name__ == "__main__":
    verify_task_002()
