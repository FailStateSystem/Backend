#!/usr/bin/env python3
"""
FailState Backend Setup Verification Script
Checks if all required files and configurations are in place.
"""

import os
import sys
from pathlib import Path

def check_file(filepath, description):
    """Check if a file exists"""
    exists = Path(filepath).exists()
    status = "✅" if exists else "❌"
    print(f"{status} {description}: {filepath}")
    return exists

def check_directory(dirpath, description):
    """Check if a directory exists"""
    exists = Path(dirpath).is_dir()
    status = "✅" if exists else "❌"
    print(f"{status} {description}: {dirpath}")
    return exists

def main():
    print("🔍 FailState Backend Setup Verification\n")
    print("=" * 60)
    
    checks = []
    
    # Core application files
    print("\n📁 Core Application Files:")
    checks.append(check_file("app/__init__.py", "App package"))
    checks.append(check_file("app/main.py", "Main application"))
    checks.append(check_file("app/config.py", "Configuration"))
    checks.append(check_file("app/database.py", "Database client"))
    checks.append(check_file("app/models.py", "Data models"))
    checks.append(check_file("app/auth.py", "Authentication"))
    
    # Router files
    print("\n🛣️  API Routers:")
    checks.append(check_file("app/routers/__init__.py", "Routers package"))
    checks.append(check_file("app/routers/auth.py", "Auth router"))
    checks.append(check_file("app/routers/users.py", "Users router"))
    checks.append(check_file("app/routers/issues.py", "Issues router"))
    checks.append(check_file("app/routers/rewards.py", "Rewards router"))
    
    # Configuration files
    print("\n⚙️  Configuration Files:")
    checks.append(check_file("requirements.txt", "Python dependencies"))
    checks.append(check_file(".env.example", "Environment template"))
    checks.append(check_file(".gitignore", "Git ignore"))
    
    # Database files
    print("\n🗄️  Database Files:")
    checks.append(check_file("database_schema.sql", "Database schema"))
    
    # Documentation files
    print("\n📚 Documentation:")
    checks.append(check_file("README.md", "Main README"))
    checks.append(check_file("QUICK_START.md", "Quick start guide"))
    checks.append(check_file("SUPABASE_SETUP.md", "Supabase setup"))
    checks.append(check_file("API_EXAMPLES.md", "API examples"))
    
    # Deployment files
    print("\n🚀 Deployment Files:")
    checks.append(check_file("Dockerfile", "Docker configuration"))
    checks.append(check_file("docker-compose.yml", "Docker Compose"))
    checks.append(check_file("start.sh", "Unix startup script"))
    checks.append(check_file("start.bat", "Windows startup script"))
    
    # Check .env file (optional but recommended)
    print("\n🔐 Environment Configuration:")
    env_exists = check_file(".env", "Environment variables")
    if not env_exists:
        print("   ⚠️  .env file not found. Run: cp .env.example .env")
    
    # Check virtual environment (optional)
    print("\n🐍 Python Environment:")
    venv_exists = check_directory("venv", "Virtual environment")
    if not venv_exists:
        print("   ℹ️  Virtual environment not created yet. Run: python3 -m venv venv")
    
    # Summary
    print("\n" + "=" * 60)
    total_checks = len(checks)
    passed_checks = sum(checks)
    
    if passed_checks == total_checks:
        print(f"✅ All checks passed! ({passed_checks}/{total_checks})")
        print("\n🎉 Your backend setup is complete!")
        print("\n📖 Next steps:")
        print("   1. Set up Supabase (see SUPABASE_SETUP.md)")
        print("   2. Configure .env file (cp .env.example .env)")
        print("   3. Run the server (./start.sh or start.bat)")
        print("   4. Visit http://localhost:8000/docs")
        return 0
    else:
        print(f"❌ Some checks failed: {passed_checks}/{total_checks} passed")
        print("\n⚠️  Please ensure all required files are present.")
        return 1

if __name__ == "__main__":
    sys.exit(main())

