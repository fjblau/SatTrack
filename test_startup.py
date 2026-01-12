#!/usr/bin/env python3
"""
Startup validation tests for Kessler application.
Checks for basic startup requirements and dependencies.
"""

import sys
import subprocess
import importlib.util
from pathlib import Path


class StartupValidator:
    def __init__(self):
        self.errors = []
        self.warnings = []
    
    def check_python_version(self):
        """Check Python version is >= 3.11"""
        version = sys.version_info
        if version.major < 3 or (version.major == 3 and version.minor < 11):
            self.errors.append(
                f"Python 3.11+ required, found {version.major}.{version.minor}.{version.micro}"
            )
            return False
        return True
    
    def check_required_modules(self):
        """Check if required Python modules are installed"""
        required_modules = [
            'fastapi',
            'uvicorn',
            'pymongo',
            'pandas',
            'numpy',
            'requests',
            'bs4',
            'pdfplumber',
            'dotenv'
        ]
        
        missing = []
        for module in required_modules:
            if importlib.util.find_spec(module) is None:
                missing.append(module)
        
        if missing:
            self.errors.append(
                f"Missing required Python modules: {', '.join(missing)}"
            )
            self.errors.append(
                "Install with: pip install -r requirements.txt"
            )
            return False
        return True
    
    def check_docker(self):
        """Check if Docker is installed and running"""
        try:
            result = subprocess.run(
                ['docker', '--version'],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode != 0:
                self.errors.append("Docker is not installed")
                return False
        except (subprocess.TimeoutExpired, FileNotFoundError):
            self.errors.append("Docker is not installed")
            return False
        
        try:
            result = subprocess.run(
                ['docker', 'info'],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode != 0:
                self.errors.append("Docker is not running")
                return False
        except subprocess.TimeoutExpired:
            self.errors.append("Docker is not responding")
            return False
        
        return True
    
    def check_nodejs(self):
        """Check if Node.js and npm are installed"""
        try:
            result = subprocess.run(
                ['node', '--version'],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode != 0:
                self.errors.append("Node.js is not installed")
                return False
        except (subprocess.TimeoutExpired, FileNotFoundError):
            self.errors.append("Node.js is not installed")
            return False
        
        try:
            result = subprocess.run(
                ['npm', '--version'],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode != 0:
                self.errors.append("npm is not installed")
                return False
        except (subprocess.TimeoutExpired, FileNotFoundError):
            self.errors.append("npm is not installed")
            return False
        
        return True
    
    def check_port_availability(self):
        """Check if required ports are available"""
        import socket
        
        ports = {
            8000: "API server",
            3000: "React dev server",
            27019: "MongoDB"
        }
        
        busy_ports = []
        for port, service in ports.items():
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            result = sock.connect_ex(('127.0.0.1', port))
            sock.close()
            
            if result == 0:
                busy_ports.append(f"{port} ({service})")
        
        if busy_ports:
            self.warnings.append(
                f"Ports already in use: {', '.join(busy_ports)}"
            )
            self.warnings.append(
                "The start.sh script will attempt to clean them up"
            )
        
        return True
    
    def check_data_files(self):
        """Check if required data files exist"""
        data_files = ['unoosa_registry.csv']
        
        missing = []
        for filename in data_files:
            if not Path(filename).exists():
                missing.append(filename)
        
        if missing:
            self.warnings.append(
                f"Data files not found: {', '.join(missing)}"
            )
            self.warnings.append(
                "Some API endpoints may not work without data files"
            )
        
        return True
    
    def validate_all(self):
        """Run all validation checks"""
        checks = [
            ("Python version", self.check_python_version),
            ("Required Python modules", self.check_required_modules),
            ("Docker", self.check_docker),
            ("Node.js and npm", self.check_nodejs),
            ("Port availability", self.check_port_availability),
            ("Data files", self.check_data_files),
        ]
        
        print("🔍 Validating startup requirements...\n")
        
        all_passed = True
        for name, check in checks:
            try:
                passed = check()
                status = "✅" if passed else "❌"
                print(f"{status} {name}")
                if not passed:
                    all_passed = False
            except Exception as e:
                print(f"❌ {name} (error: {e})")
                self.errors.append(f"{name} check failed: {e}")
                all_passed = False
        
        if self.warnings:
            print("\n⚠️  Warnings:")
            for warning in self.warnings:
                print(f"  - {warning}")
        
        if self.errors:
            print("\n❌ Errors:")
            for error in self.errors:
                print(f"  - {error}")
            print("\n⛔ Startup validation failed")
            return False
        
        print("\n✅ All startup requirements validated successfully")
        return all_passed


def main():
    """Main entry point for standalone execution"""
    validator = StartupValidator()
    success = validator.validate_all()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
