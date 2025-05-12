#!/usr/bin/env python3
"""
Tests for repositories functionality
"""

import os
import unittest
import tempfile
import json
from unittest import mock

from migrator.utils.repositories import Repository, RepositoryManager
from migrator.utils.distro import DistroInfo

class TestRepository(unittest.TestCase):
    """Test Repository class"""
    
    def test_to_dict(self):
        """Test converting a repository to dictionary"""
        repo = Repository(
            repo_id="test:repo",
            name="Test Repo",
            enabled=True,
            url="http://test.repo",
            distro_type="ubuntu",
            repo_type="apt"
        )
        
        repo_dict = repo.to_dict()
        
        self.assertEqual(repo_dict["repo_id"], "test:repo")
        self.assertEqual(repo_dict["name"], "Test Repo")
        self.assertEqual(repo_dict["enabled"], True)
        self.assertEqual(repo_dict["url"], "http://test.repo")
        self.assertEqual(repo_dict["distro_type"], "ubuntu")
        self.assertEqual(repo_dict["repo_type"], "apt")
    
    def test_from_dict(self):
        """Test creating a repository from dictionary"""
        repo_dict = {
            "repo_id": "test:repo",
            "name": "Test Repo",
            "enabled": True,
            "url": "http://test.repo",
            "distro_type": "ubuntu",
            "repo_type": "apt"
        }
        
        repo = Repository.from_dict(repo_dict)
        
        self.assertEqual(repo.repo_id, "test:repo")
        self.assertEqual(repo.name, "Test Repo")
        self.assertEqual(repo.enabled, True)
        self.assertEqual(repo.url, "http://test.repo")
        self.assertEqual(repo.distro_type, "ubuntu")
        self.assertEqual(repo.repo_type, "apt")
    
    def test_is_compatible_with(self):
        """Test repository compatibility checking"""
        # Test same distro compatibility
        repo = Repository(
            repo_id="test:repo",
            name="Test Repo",
            enabled=True,
            url="http://test.repo",
            distro_type="ubuntu",
            repo_type="apt"
        )
        
        distro_info = DistroInfo(id="ubuntu", name="Ubuntu", version="20.04")
        self.assertTrue(repo.is_compatible_with(distro_info))
        
        # Test compatibility within Debian family
        distro_info = DistroInfo(id="linuxmint", name="Linux Mint", version="20")
        self.assertTrue(repo.is_compatible_with(distro_info))
        
        # Test incompatibility across distro families
        distro_info = DistroInfo(id="fedora", name="Fedora", version="33")
        self.assertFalse(repo.is_compatible_with(distro_info))
        
        # Test Flatpak compatibility across distros
        flatpak_repo = Repository(
            repo_id="flatpak:test:user",
            name="Test Flatpak",
            enabled=True,
            url="https://flatpak.test",
            distro_type="ubuntu",
            repo_type="flatpak"
        )
        
        distro_info = DistroInfo(id="fedora", name="Fedora", version="33")
        self.assertTrue(flatpak_repo.is_compatible_with(distro_info))
    
    def test_get_compatibility_issue(self):
        """Test getting compatibility issues"""
        # Test compatible repo
        repo = Repository(
            repo_id="test:repo",
            name="Test Repo",
            enabled=True,
            url="http://test.repo",
            distro_type="ubuntu",
            repo_type="apt"
        )
        
        distro_info = DistroInfo(id="ubuntu", name="Ubuntu", version="20.04")
        self.assertIsNone(repo.get_compatibility_issue(distro_info))
        
        # Test incompatible repo
        distro_info = DistroInfo(id="fedora", name="Fedora", version="33")
        issue = repo.get_compatibility_issue(distro_info)
        self.assertIsNotNone(issue)
        self.assertIn("APT repository from ubuntu cannot be used with Fedora", issue)
        
        # Test PPA incompatibility
        ppa_repo = Repository(
            repo_id="ppa:test/test",
            name="Test PPA",
            enabled=True,
            url="ppa:test/test",
            distro_type="ubuntu",
            repo_type="ppa"
        )
        
        distro_info = DistroInfo(id="debian", name="Debian", version="11")
        issue = ppa_repo.get_compatibility_issue(distro_info)
        self.assertIsNotNone(issue)
        self.assertIn("Ubuntu PPA cannot be used with Debian", issue)

class TestRepositoryManager(unittest.TestCase):
    """Test RepositoryManager class"""
    
    @mock.patch('migrator.utils.repositories.get_distro_info')
    def test_init(self, mock_get_distro_info):
        """Test initialization"""
        mock_get_distro_info.return_value = DistroInfo(id="ubuntu", name="Ubuntu", version="20.04")
        
        manager = RepositoryManager()
        
        self.assertEqual(manager.distro_info.id, "ubuntu")
        self.assertEqual(manager.distro_info.name, "Ubuntu")
        self.assertEqual(manager.distro_info.version, "20.04")
        self.assertEqual(len(manager.repositories), 0)
    
    @mock.patch('migrator.utils.repositories.get_distro_info')
    def test_export_repositories(self, mock_get_distro_info):
        """Test exporting repositories"""
        mock_get_distro_info.return_value = DistroInfo(id="ubuntu", name="Ubuntu", version="20.04")
        
        manager = RepositoryManager()
        manager.repositories = [
            Repository(
                repo_id="test:repo",
                name="Test Repo",
                enabled=True,
                url="http://test.repo",
                distro_type="ubuntu",
                repo_type="apt"
            )
        ]
        
        export_data = manager.export_repositories()
        
        self.assertEqual(export_data["distro_info"]["id"], "ubuntu")
        self.assertEqual(export_data["distro_info"]["name"], "Ubuntu")
        self.assertEqual(export_data["distro_info"]["version"], "20.04")
        self.assertEqual(len(export_data["repositories"]), 1)
        self.assertEqual(export_data["repositories"][0]["repo_id"], "test:repo")
    
    @mock.patch('migrator.utils.repositories.get_distro_info')
    def test_check_compatibility(self, mock_get_distro_info):
        """Test checking compatibility"""
        mock_get_distro_info.return_value = DistroInfo(id="fedora", name="Fedora", version="33")
        
        manager = RepositoryManager()
        
        # Create test backup data with compatible and incompatible repos
        backup_data = {
            "repositories": [
                {
                    "repo_id": "apt:test",
                    "name": "APT Repo",
                    "enabled": True,
                    "url": "http://test.repo",
                    "distro_type": "ubuntu",
                    "repo_type": "apt"
                },
                {
                    "repo_id": "dnf:test",
                    "name": "DNF Repo",
                    "enabled": True,
                    "url": "http://test.repo",
                    "distro_type": "fedora",
                    "repo_type": "dnf"
                },
                {
                    "repo_id": "flatpak:test:user",
                    "name": "Flatpak Remote",
                    "enabled": True,
                    "url": "https://flatpak.test",
                    "distro_type": "ubuntu",
                    "repo_type": "flatpak"
                }
            ]
        }
        
        issues = manager.check_compatibility(backup_data)
        
        # Should find one incompatible repo (the APT one)
        self.assertEqual(len(issues), 1)
        self.assertEqual(issues[0]["repo_id"], "apt:test")
        self.assertEqual(issues[0]["repo_type"], "apt")
        self.assertIn("APT repository from ubuntu cannot be used with Fedora", issues[0]["issue"])
    
    @mock.patch('migrator.utils.repositories.RepositoryManager._restore_apt_repositories')
    @mock.patch('migrator.utils.repositories.RepositoryManager._restore_dnf_repositories')
    @mock.patch('migrator.utils.repositories.RepositoryManager.check_compatibility')
    @mock.patch('migrator.utils.repositories.get_distro_info')
    def test_restore_repositories(self, mock_get_distro_info, mock_check_compatibility,
                                 mock_restore_dnf, mock_restore_apt):
        """Test repository restoration"""
        mock_get_distro_info.return_value = DistroInfo(id="fedora", name="Fedora", version="33")
        
        # Setup compatibility issues for the APT repo only
        mock_check_compatibility.return_value = [
            {
                "repo_id": "apt:test",
                "name": "APT Repo",
                "repo_type": "apt",
                "distro_type": "ubuntu",
                "issue": "APT repository from ubuntu cannot be used with Fedora"
            }
        ]
        
        # Setup mock return values for restoration functions
        mock_restore_apt.return_value = (["Added APT repo"], [])
        mock_restore_dnf.return_value = (["Added DNF repo"], [])
        
        manager = RepositoryManager()
        
        # Create test backup data with both types of repos
        backup_data = {
            "repositories": [
                {
                    "repo_id": "apt:test",
                    "name": "APT Repo",
                    "enabled": True,
                    "url": "http://test.repo",
                    "distro_type": "ubuntu",
                    "repo_type": "apt"
                },
                {
                    "repo_id": "dnf:test",
                    "name": "DNF Repo",
                    "enabled": True,
                    "url": "http://test.repo",
                    "distro_type": "fedora",
                    "repo_type": "dnf"
                }
            ]
        }
        
        # Test dry run mode
        successes, issues = manager.restore_repositories(backup_data, dry_run=True)
        
        # Should show what would be restored (only the compatible DNF repo)
        self.assertEqual(len(successes), 1)
        self.assertEqual(len(issues), 1)
        self.assertIn("compatibility", issues[0]["type"])
        self.assertFalse(mock_restore_apt.called)
        self.assertFalse(mock_restore_dnf.called)
        
        # Reset mocks
        mock_restore_apt.reset_mock()
        mock_restore_dnf.reset_mock()
        
        # Test actual restoration
        successes, issues = manager.restore_repositories(backup_data, dry_run=False)
        
        # Should restore only the compatible DNF repo
        self.assertEqual(len(successes), 1)
        self.assertEqual(len(issues), 1)
        self.assertFalse(mock_restore_apt.called)
        self.assertTrue(mock_restore_dnf.called)

if __name__ == '__main__':
    unittest.main() 