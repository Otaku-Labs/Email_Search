#!/usr/bin/env python3

import os
import sys
import argparse
from pathlib import Path
import mimetypes
from typing import Set, List, Generator
import re

class EmailDomainSearcher:
    def __init__(self, search_path: str, exclude_dirs_file: str = "exclude_dirs.txt", 
                 output_file: str = "search_results.txt"):
        self.search_path = Path(search_path).resolve()
        self.exclude_dirs_file = Path(exclude_dirs_file)
        self.output_file = Path(output_file)
        self.domain = ""
        self.excluded_dirs: Set[str] = set()
        
        # Common binary file extensions to skip
        self.binary_extensions = {
            '.exe', '.bin', '.so', '.dll', '.dylib', '.a', '.o', '.obj', '.class',
            '.jar', '.war', '.ear', '.zip', '.gz', '.tar', '.bz2', '.xz', '.7z',
            '.rar', '.pdf', '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx',
            '.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff', '.ico', '.svg',
            '.mp3', '.mp4', '.avi', '.mov', '.wmv', '.flv', '.mkv', '.webm',
            '.iso', '.dmg', '.img', '.deb', '.rpm', '.msi', '.woff', '.woff2',
            '.ttf', '.otf', '.eot', '.pyc', '.pyo', '.pyd'
        }
    
    def get_domain(self) -> str:
        """Get email domain from user input"""
        if not self.domain:
            domain = input("Enter the email domain: ").strip()
            if not domain.startswith('@'):
                domain = '@' + domain
            self.domain = domain
            print(f"Set domain to {self.domain}")
        return self.domain
    
    def create_default_exclude_file(self) -> None:
        """Create default exclude directories file"""
        default_excludes = [
            "# Directories to exclude from search (one per line)",
            "# Lines starting with # are comments",
            "logs", ".git", ".svn", ".hg", "node_modules", ".npm", ".yarn",
            "vendor", "cache", "tmp", "temp", ".cache", "build", "dist",
            "target", ".idea", ".vscode", ".DS_Store", "__pycache__",
            "*.egg-info", ".pytest_cache", ".coverage", "htmlcov",
            ".tox", ".venv", "venv", "env", ".mypy_cache", ".terraform",
            "bower_components", "jspm_packages", "web_modules"
        ]
        
        with open(self.exclude_dirs_file, 'w') as f:
            f.write('\n'.join(default_excludes) + '\n')
        print(f"Created default exclude file: {self.exclude_dirs_file}")
    
    def load_excluded_dirs(self) -> None:
        """Load excluded directories from file"""
        if not self.exclude_dirs_file.exists():
            print(f"Exclude directories file \"{self.exclude_dirs_file}\" not found. Creating default...")
            self.create_default_exclude_file()
        
        with open(self.exclude_dirs_file, 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#'):
                    self.excluded_dirs.add(line)
    
    def is_excluded_dir(self, dir_path: Path) -> bool:
        """Check if directory should be excluded"""
        dir_name = dir_path.name
        return dir_name in self.excluded_dirs
    
    def is_binary_file(self, file_path: Path) -> bool:
        """Check if file is likely binary"""
        # Check extension first (fastest)
        if file_path.suffix.lower() in self.binary_extensions:
            if hasattr(self, 'debug') and self.debug:
                print(f"DEBUG: {file_path} flagged as binary due to extension {file_path.suffix}")
            return True
        
        # Check MIME type
        mime_type, _ = mimetypes.guess_type(str(file_path))
        if mime_type:
            if not mime_type.startswith('text/') and mime_type != 'application/json' and mime_type != 'application/xml' and mime_type != 'text/xml':
                if hasattr(self, 'debug') and self.debug:
                    print(f"DEBUG: {file_path} flagged as binary due to MIME type {mime_type}")
                return True
        
        # Check for null bytes in first 1024 bytes
        try:
            with open(file_path, 'rb') as f:
                chunk = f.read(1024)
                if b'\0' in chunk:
                    if hasattr(self, 'debug') and self.debug:
                        print(f"DEBUG: {file_path} flagged as binary due to null bytes")
                    return True
        except (OSError, IOError):
            if hasattr(self, 'debug') and self.debug:
                print(f"DEBUG: {file_path} flagged as binary due to read error")
            return True
        
        if hasattr(self, 'debug') and self.debug:
            print(f"DEBUG: {file_path} detected as text file")
        return False
    
    def search_file_content(self, file_path: Path, domain: str) -> bool:
        """Search for domain in file content"""
        if self.is_binary_file(file_path):
            if hasattr(self, 'debug') and self.debug:
                print(f"DEBUG: Skipping binary file: {file_path}")
            return False
        
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
                found = domain in content
                if hasattr(self, 'debug') and self.debug:
                    print(f"DEBUG: Searching {file_path} for '{domain}' -> {'FOUND' if found else 'NOT FOUND'}")
                    if found:
                        # Show the line where it was found
                        lines = content.split('\n')
                        for i, line in enumerate(lines, 1):
                            if domain in line:
                                print(f"DEBUG: Found on line {i}: {line.strip()}")
                                break
                return found
        except (OSError, IOError, UnicodeDecodeError):
            # Try with different encoding
            try:
                with open(file_path, 'r', encoding='latin-1', errors='ignore') as f:
                    content = f.read()
                    found = domain in content
                    if hasattr(self, 'debug') and self.debug:
                        print(f"DEBUG: Searching {file_path} (latin-1) for '{domain}' -> {'FOUND' if found else 'NOT FOUND'}")
                    return found
            except (OSError, IOError):
                if hasattr(self, 'debug') and self.debug:
                    print(f"DEBUG: Cannot read file: {file_path}")
                return False
    
    def find_files(self) -> Generator[Path, None, None]:
        """Generator that yields all files to search"""
        total_files = 0
        excluded_dirs = 0
        
        for root, dirs, files in os.walk(self.search_path):
            root_path = Path(root)
            
            # Filter out excluded directories
            original_dirs = dirs[:]
            dirs[:] = [d for d in dirs if not self.is_excluded_dir(root_path / d)]
            
            if hasattr(self, 'debug') and self.debug:
                excluded_here = set(original_dirs) - set(dirs)
                if excluded_here:
                    excluded_dirs += len(excluded_here)
                    print(f"DEBUG: Excluding directories in {root_path}: {excluded_here}")
            
            for file_name in files:
                file_path = root_path / file_name
                if file_path.is_file():
                    total_files += 1
                    if hasattr(self, 'debug') and self.debug and total_files <= 10:
                        print(f"DEBUG: Found file: {file_path}")
                    yield file_path
        
        if hasattr(self, 'debug') and self.debug:
            print(f"DEBUG: Total files found: {total_files}")
            print(f"DEBUG: Total directories excluded: {excluded_dirs}")
    
    def search_domain(self) -> List[Path]:
        """Search for domain in all files"""
        domain = self.get_domain()
        self.load_excluded_dirs()
        
        print(f"Searching for domain '{domain}' in files under: {self.search_path}")
        print(f"Using exclude directories from: {self.exclude_dirs_file}")
        print(f"Results will be saved in {self.output_file}")
        print("=" * 70)
        print("Scanning files...")
        print("Note: Binary files and common non-text files are automatically skipped")
        print()
        
        matching_files = []
        file_count = 0
        
        for file_path in self.find_files():
            file_count += 1
            if file_count % 100 == 0:
                print(f"Scanned {file_count} files...", end='\r')
            
            if hasattr(self, 'debug') and self.debug:
                print(f"DEBUG: Processing file: {file_path}")
            
            if self.search_file_content(file_path, domain):
                matching_files.append(file_path)
        
        print(f"\nProcessed {file_count} files total")
        
        if hasattr(self, 'debug') and self.debug:
            print(f"DEBUG: Found {len(matching_files)} matching files")
            for f in matching_files:
                print(f"DEBUG: Match: {f}")
        
        return sorted(set(matching_files))
    
    def save_results(self, results: List[Path]) -> None:
        """Save results to output file"""
        with open(self.output_file, 'w') as f:
            for file_path in results:
                f.write(str(file_path) + '\n')
    
    def run(self) -> None:
        """Main execution method"""
        if not self.search_path.exists():
            print(f"Error: Directory \"{self.search_path}\" does not exist.")
            sys.exit(1)
        
        if not self.search_path.is_dir():
            print(f"Error: \"{self.search_path}\" is not a directory.")
            sys.exit(1)
        
        results = self.search_domain()
        self.save_results(results)
        
        print("=" * 70)
        print("Search complete!")
        print(f"Found {len(results)} files containing '{self.domain}'")
        print(f"Results saved to: {self.output_file}")
        
        # Show sample results
        if results:
            print("\nSample results:")
            for file_path in results[:10]:
                print(f"  {file_path}")
            if len(results) > 10:
                print(f"  ... and {len(results) - 10} more files")


def main():
    parser = argparse.ArgumentParser(
        description="Search for email domain in files",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s                                    # Search current directory
  %(prog)s /path/to/search                    # Search specific directory  
  %(prog)s /path/to/search -e my_exclude.txt  # Use custom exclude file
  %(prog)s -o results.txt                     # Use custom output file
        """
    )
    
    parser.add_argument(
        'search_path', 
        nargs='?', 
        default='.',
        help='Directory to search (default: current directory)'
    )
    
    parser.add_argument(
        '-e', '--exclude-dirs',
        default='exclude_dirs.txt',
        help='File containing directories to exclude (default: exclude_dirs.txt)'
    )
    
    parser.add_argument(
        '-o', '--output',
        default='search_results.txt',
        help='Output file for results (default: search_results.txt)'
    )
    
    parser.add_argument(
        '-d', '--domain',
        help='Email domain to search for (will prompt if not provided)'
    )
    
    parser.add_argument(
        '--debug',
        action='store_true',
        help='Enable debug output to see what files are being processed'
    )
    
    args = parser.parse_args()
    
    searcher = EmailDomainSearcher(
        search_path=args.search_path,
        exclude_dirs_file=args.exclude_dirs,
        output_file=args.output
    )
    
    if args.debug:
        searcher.debug = True
    
    if args.domain:
        if not args.domain.startswith('@'):
            args.domain = '@' + args.domain
        searcher.domain = args.domain
    
    try:
        searcher.run()
    except KeyboardInterrupt:
        print("\nSearch interrupted by user.")
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()