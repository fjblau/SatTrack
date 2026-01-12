#!/usr/bin/env python3
"""
Unit tests for startup validation functionality.
Tests various failure scenarios to ensure validation catches startup issues.
"""

import unittest
import sys
from unittest.mock import patch, MagicMock
from test_startup import StartupValidator


class TestStartupValidator(unittest.TestCase):
    """Test suite for StartupValidator class"""
    
    def setUp(self):
        """Create validator instance for each test"""
        self.validator = StartupValidator()
    
    def test_python_version_check_success(self):
        """Test Python version check passes for valid version"""
        result = self.validator.check_python_version()
        self.assertTrue(result)
        self.assertEqual(len(self.validator.errors), 0)
    
    def test_python_version_check_failure(self):
        """Test Python version check fails for old version"""
        from collections import namedtuple
        VersionInfo = namedtuple('VersionInfo', ['major', 'minor', 'micro', 'releaselevel', 'serial'])
        mock_version = VersionInfo(3, 10, 0, 'final', 0)
        
        with patch('sys.version_info', mock_version):
            result = self.validator.check_python_version()
            self.assertFalse(result)
            self.assertGreater(len(self.validator.errors), 0)
            self.assertIn('3.11+', self.validator.errors[0])
    
    def test_required_modules_check_success(self):
        """Test required modules check passes when all modules present"""
        result = self.validator.check_required_modules()
        self.assertTrue(result)
        self.assertEqual(len(self.validator.errors), 0)
    
    def test_required_modules_check_failure(self):
        """Test required modules check fails when module is missing"""
        with patch('importlib.util.find_spec', return_value=None):
            result = self.validator.check_required_modules()
            self.assertFalse(result)
            self.assertGreater(len(self.validator.errors), 0)
            self.assertIn('Missing required Python modules', self.validator.errors[0])
    
    def test_docker_not_installed(self):
        """Test Docker check fails when Docker not installed"""
        with patch('subprocess.run', side_effect=FileNotFoundError()):
            result = self.validator.check_docker()
            self.assertFalse(result)
            self.assertIn('Docker is not installed', self.validator.errors)
    
    def test_docker_not_running(self):
        """Test Docker check fails when Docker not running"""
        mock_result = MagicMock()
        mock_result.returncode = 0
        
        mock_result_not_running = MagicMock()
        mock_result_not_running.returncode = 1
        
        with patch('subprocess.run', side_effect=[mock_result, mock_result_not_running]):
            result = self.validator.check_docker()
            self.assertFalse(result)
            self.assertIn('Docker is not running', self.validator.errors)
    
    def test_nodejs_not_installed(self):
        """Test Node.js check fails when Node.js not installed"""
        with patch('subprocess.run', side_effect=FileNotFoundError()):
            result = self.validator.check_nodejs()
            self.assertFalse(result)
            self.assertIn('Node.js is not installed', self.validator.errors)
    
    def test_port_availability_warning(self):
        """Test port check generates warning for busy ports"""
        import socket
        original_connect_ex = socket.socket.connect_ex
        
        def mock_connect_ex(self, addr):
            if addr[1] == 8000:
                return 0
            return 1
        
        with patch.object(socket.socket, 'connect_ex', mock_connect_ex):
            result = self.validator.check_port_availability()
            self.assertTrue(result)
            self.assertGreater(len(self.validator.warnings), 0)
            self.assertTrue(any('8000' in w for w in self.validator.warnings))
    
    def test_data_files_warning(self):
        """Test data files check generates warning for missing files"""
        with patch('pathlib.Path.exists', return_value=False):
            result = self.validator.check_data_files()
            self.assertTrue(result)
            self.assertGreater(len(self.validator.warnings), 0)
            self.assertTrue(any('unoosa_registry.csv' in w for w in self.validator.warnings))
    
    def test_validate_all_success(self):
        """Test validate_all returns True when all checks pass"""
        with patch.object(self.validator, 'check_python_version', return_value=True), \
             patch.object(self.validator, 'check_required_modules', return_value=True), \
             patch.object(self.validator, 'check_docker', return_value=True), \
             patch.object(self.validator, 'check_nodejs', return_value=True), \
             patch.object(self.validator, 'check_port_availability', return_value=True), \
             patch.object(self.validator, 'check_data_files', return_value=True):
            result = self.validator.validate_all()
            self.assertTrue(result)
    
    def test_validate_all_failure(self):
        """Test validate_all returns False when any check fails"""
        with patch.object(self.validator, 'check_python_version', return_value=False), \
             patch.object(self.validator, 'check_required_modules', return_value=True), \
             patch.object(self.validator, 'check_docker', return_value=True), \
             patch.object(self.validator, 'check_nodejs', return_value=True), \
             patch.object(self.validator, 'check_port_availability', return_value=True), \
             patch.object(self.validator, 'check_data_files', return_value=True):
            self.validator.errors.append("Test error")
            result = self.validator.validate_all()
            self.assertFalse(result)


class TestStartupScenarios(unittest.TestCase):
    """Integration tests for common startup scenarios"""
    
    def test_uvicorn_missing_scenario(self):
        """Test detection of missing uvicorn module (original bug)"""
        validator = StartupValidator()
        
        with patch('importlib.util.find_spec') as mock_find_spec:
            def find_spec_side_effect(module_name):
                if module_name == 'uvicorn':
                    return None
                return MagicMock()
            
            mock_find_spec.side_effect = find_spec_side_effect
            
            result = validator.check_required_modules()
            self.assertFalse(result)
            self.assertTrue(any('uvicorn' in e for e in validator.errors))
    
    def test_python_too_old_scenario(self):
        """Test detection of Python version too old"""
        from collections import namedtuple
        validator = StartupValidator()
        
        VersionInfo = namedtuple('VersionInfo', ['major', 'minor', 'micro', 'releaselevel', 'serial'])
        mock_version = VersionInfo(3, 9, 0, 'final', 0)
        
        with patch('sys.version_info', mock_version):
            result = validator.check_python_version()
            self.assertFalse(result)
            self.assertTrue(any('3.11+' in e for e in validator.errors))


def run_tests():
    """Run all tests and return success status"""
    suite = unittest.TestLoader().loadTestsFromModule(sys.modules[__name__])
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    return result.wasSuccessful()


if __name__ == '__main__':
    success = run_tests()
    sys.exit(0 if success else 1)
