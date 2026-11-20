#!/usr/bin/env python3
"""
Test script to verify PACTLINE DevOps voice tools are properly installed.
"""

import json
import urllib.request
import urllib.error
import sys
from pathlib import Path
from dotenv import load_dotenv
import os

backend_dir = Path(__file__).parent / "backend"
load_dotenv(backend_dir / ".env")

def test_backend():
    """Check if backend is running and healthy."""
    try:
        with urllib.request.urlopen("http://localhost:8000/health", timeout=5) as r:
            data = json.loads(r.read())
            assert data["status"] == "ok"
            print("[OK] Backend is running (port 8000)")
            return True
    except Exception as e:
        print(f"[FAIL] Backend not responding: {e}")
        return False

def test_database():
    """Check if database exists and is accessible."""
    db_path = backend_dir / "pactline.db"
    if db_path.exists():
        print(f"[OK] Database found at {db_path}")
        return True
    else:
        print(f"[FAIL] Database not found at {db_path}")
        return False

def test_env_vars():
    """Check if all required env vars are set."""
    required = {
        "LLM_API_KEY": "Groq API key",
        "LLM_URL": "LLM endpoint",
        "GITHUB_TOKEN": "GitHub personal access token",
        "JENKINS_BASE_URL": "Jenkins URL",
        "JENKINS_USERNAME": "Jenkins username",
        "JENKINS_API_TOKEN": "Jenkins API token",
        "AGORA_APP_ID": "Agora app ID",
        "MURF_API_KEY": "Murf API key",
        "SONARQUBE_TOKEN": "SonarQube API token",
    }
    
    all_good = True
    for key, desc in required.items():
        value = os.environ.get(key)
        if value:
            display = value[:20] + "..." if len(value) > 20 else value
            print(f"[OK] {key}: {display}")
        else:
            print(f"[FAIL] {key} not set ({desc})")
            all_good = False
    return all_good

def test_tool_imports():
    """Check if all tool components can be imported."""
    sys.path.insert(0, str(backend_dir))
    
    try:
        from app.domain.tools import ToolRegistry
        print("[OK] ToolRegistry imports successfully")
        
        for method in ['_list_repos', '_generate_pipeline', '_create_pr', '_analyze_sonar']:
            if hasattr(ToolRegistry, method):
                print(f"[OK] Tool handler {method} exists")
            else:
                print(f"[FAIL] Tool handler {method} not found")
                return False
        
        return True
    except Exception as e:
        print(f"[FAIL] Tool import failed: {e}")
        return False

def test_github_integration():
    """Test GitHub client can be instantiated."""
    sys.path.insert(0, str(backend_dir))
    
    try:
        from app.integrations.github import GitHubClient
        from app.integrations.http import urllib_transport
        
        client = GitHubClient.from_env(os.environ, urllib_transport)
        if client:
            print("[OK] GitHub client initialized with token")
            return True
        else:
            print("[FAIL] GitHub token not configured")
            return False
    except Exception as e:
        print(f"[FAIL] GitHub integration failed: {e}")
        return False

def test_sonarqube_integration():
    """Test SonarQube client can be instantiated."""
    sys.path.insert(0, str(backend_dir))
    
    try:
        from app.integrations.sonarqube import SonarQubeClient
        from app.integrations.http import urllib_transport
        
        client = SonarQubeClient.from_env(os.environ, urllib_transport)
        if client:
            print("[OK] SonarQube client initialized with token")
            
            project_key = os.environ.get("SONARQUBE_PROJECT_KEY", "PrathamM16_PACTLINE")
            summary = client.get_quality_summary(project_key)
            
            if "quality_gate_passed" in summary:
                print(f"[OK] Quality analysis available for {project_key}")
                print(f"     Gate Status: {summary.get('quality_gate_status')}")
                print(f"     Bugs: {summary.get('bugs')}, Vulns: {summary.get('vulnerabilities')}")
                return True
            else:
                print("[FAIL] Quality summary format invalid")
                return False
        else:
            print("[FAIL] SonarQube token not configured")
            return False
    except Exception as e:
        print(f"[FAIL] SonarQube integration failed: {e}")
        return False

def test_pipeline_generator():
    """Test pipeline generator can create Jenkinsfile."""
    sys.path.insert(0, str(backend_dir))
    
    try:
        from app.devops.pipeline import PipelineSpec, generate_jenkinsfile, validate_spec
        
        spec = PipelineSpec(
            job_name="test-job",
            repository="user/repo",
            branch="main",
            app_type="angular",
            node_version="20",
            stages=("install", "lint", "unit_tests"),
            sonar_project_key=None
        )
        
        errors = validate_spec(spec)
        if errors:
            print(f"[FAIL] Pipeline spec validation failed: {errors}")
            return False
        
        content = generate_jenkinsfile(spec)
        if content and "pipeline" in content and "nodejs" in content.lower():
            lines = content.count('\n')
            print(f"[OK] Pipeline generator creates valid Jenkinsfile ({lines} lines)")
            return True
        else:
            print("[FAIL] Generated Jenkinsfile is empty or invalid")
            return False
    except Exception as e:
        print(f"[FAIL] Pipeline generator failed: {e}")
        return False

def main():
    """Run all tests."""
    print("=" * 60)
    print("PACTLINE DevOps Voice Tools - Verification Report")
    print("=" * 60)
    print()
    
    tests = [
        ("Backend Health", test_backend),
        ("Database", test_database),
        ("Environment Variables", test_env_vars),
        ("Tool Imports", test_tool_imports),
        ("GitHub Integration", test_github_integration),
        ("SonarQube Integration", test_sonarqube_integration),
        ("Pipeline Generator", test_pipeline_generator),
    ]
    
    results = {}
    for name, test_func in tests:
        print(f"\n[{name}]")
        print("-" * 60)
        try:
            results[name] = test_func()
        except Exception as e:
            print(f"[FAIL] Test crashed: {e}")
            results[name] = False
    
    print()
    print("=" * 60)
    print("Summary:")
    print("=" * 60)
    
    passed = sum(1 for r in results.values() if r)
    total = len(results)
    
    for name, result in results.items():
        status = "[PASS]" if result else "[FAIL]"
        print(f"{status} - {name}")
    
    print()
    print(f"Result: {passed}/{total} tests passed")
    
    if passed == total:
        print()
        print("[SUCCESS] All systems ready! You can now:")
        print("   1. Visit http://localhost:4200")
        print("   2. Login with qa-tester@example.com / QaTester-12345")
        print("   3. Click Voice room")
        print("   4. Try commands like:")
        print("      - 'List my repositories'")
        print("      - 'Create a pipeline for PrathamM16/PACTLINE'")
        print("      - 'Analyze the code quality of PrathamM16_PACTLINE'")
        return 0
    else:
        print()
        print("[FAILED] Some systems are not ready. Check errors above.")
        return 1

if __name__ == "__main__":
    sys.exit(main())
