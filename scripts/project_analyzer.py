#!/usr/bin/env python3
"""
Project analyzer for year review.
Groups related activities and detects project timelines.
"""

import re
from datetime import datetime, timedelta
from typing import Dict, List, Set, Optional
from collections import defaultdict


class ProjectAnalyzer:
    def __init__(self, project_keywords: Dict[str, List[str]]):
        self.project_keywords = project_keywords
        self.projects = {}
        
    def _extract_keywords(self, text: str) -> Set[str]:
        """Extract project-related keywords from text."""
        if not text:
            return set()
        
        text_lower = text.lower()
        found_keywords = set()
        
        for category, keywords in self.project_keywords.items():
            for keyword in keywords:
                if keyword.lower() in text_lower:
                    found_keywords.add(category)
                    break
        
        return found_keywords
    
    def _detect_project_name(self, text: str) -> Optional[str]:
        """Try to detect project name from text."""
        if not text:
            return None
        
        # Common patterns
        patterns = [
            r'(\w+)\s+(?:v2|v3|phase\s+\d+|kickoff|integration|implementation)',
            r'(?:kickoff|review|sync|meeting):\s*([A-Z][a-zA-Z\s]+)',
            r'([A-Z][a-zA-Z]+)\s+(?:project|initiative|effort)',
            r'([A-Z][a-zA-Z]+)\s+(?:by|from|with)',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                name = match.group(1).strip()
                if len(name) > 2:
                    return name
        
        # Extract capitalized words (potential project names)
        words = re.findall(r'\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\b', text)
        if words:
            # Return first substantial capitalized phrase
            for word in words[:3]:
                if len(word) > 3 and word.lower() not in ['the', 'and', 'for', 'with', 'from']:
                    return word
        
        return None
    
    def _categorize_project(self, keywords: Set[str], title: str) -> str:
        """Categorize project based on keywords and title."""
        title_lower = title.lower()
        
        # Priority order
        if 'ai' in keywords or 'klaudia' in title_lower or 'remediation' in title_lower:
            return 'ai'
        elif 'security' in keywords or 'rbac' in title_lower or 'auth' in title_lower:
            return 'security'
        elif 'cost' in keywords or 'finops' in title_lower or 'hpa' in title_lower:
            return 'cost'
        elif 'performance' in keywords or 'perf' in title_lower or 'optimize' in title_lower:
            return 'perf'
        elif 'infrastructure' in keywords or 'infra' in title_lower or 'deployment' in title_lower:
            return 'infra'
        elif 'team' in keywords or 'interview' in title_lower or 'hiring' in title_lower:
            return 'team'
        else:
            return 'feature'
    
    def _get_icon_class(self, category: str) -> str:
        """Get icon class for project category."""
        icon_map = {
            'infra': 'icon-infra',
            'feature': 'icon-feature',
            'perf': 'icon-perf',
            'security': 'icon-security',
            'ai': 'icon-ai',
            'cost': 'icon-cost',
            'team': 'icon-team'
        }
        return icon_map.get(category, 'icon-feature')
    
    def _get_icon_emoji(self, category: str) -> str:
        """Get emoji icon for project category."""
        emoji_map = {
            'infra': '🏗️',
            'feature': '⚓',
            'perf': '⚡',
            'security': '🔐',
            'ai': '🧠',
            'cost': '💰',
            'team': '👥'
        }
        return emoji_map.get(category, '📦')
    
    def analyze_prs(self, prs: List[Dict]) -> Dict[str, List[Dict]]:
        """Group PRs by project."""
        project_prs = defaultdict(list)
        
        for pr in prs:
            title = pr.get('title', '')
            body = pr.get('body', '')
            text = f"{title} {body}"
            
            keywords = self._extract_keywords(text)
            project_name = self._detect_project_name(title) or self._detect_project_name(body)
            
            if not project_name:
                # Try to infer from keywords
                if keywords:
                    project_name = f"{list(keywords)[0].title()} Initiative"
                else:
                    project_name = "Other Work"
            
            project_prs[project_name].append(pr)
        
        return dict(project_prs)
    
    def analyze_calendar_events(self, events: List[Dict]) -> Dict[str, List[Dict]]:
        """Group calendar events by project."""
        project_events = defaultdict(list)
        
        for event in events:
            title = event.get('title', '')
            description = event.get('description', '')
            text = f"{title} {description}"
            
            keywords = self._extract_keywords(text)
            project_name = self._detect_project_name(title) or self._detect_project_name(description)
            
            if not project_name:
                # Try to infer from keywords
                if keywords:
                    project_name = f"{list(keywords)[0].title()} Initiative"
                else:
                    # Skip generic events
                    continue
            
            project_events[project_name].append(event)
        
        return dict(project_events)
    
    def merge_projects(self, pr_projects: Dict, event_projects: Dict) -> Dict[str, Dict]:
        """Merge PR and event projects into unified project structure."""
        all_project_names = set(pr_projects.keys()) | set(event_projects.keys())
        merged = {}
        
        for project_name in all_project_names:
            prs = pr_projects.get(project_name, [])
            events = event_projects.get(project_name, [])
            
            if not prs and not events:
                continue
            
            # Determine project details from first PR or event
            sample_text = ""
            if prs:
                sample_text = f"{prs[0].get('title', '')} {prs[0].get('body', '')}"
            elif events:
                sample_text = f"{events[0].get('title', '')} {events[0].get('description', '')}"
            
            keywords = self._extract_keywords(sample_text)
            category = self._categorize_project(keywords, project_name)
            
            # Get date range
            dates = []
            for pr in prs:
                if pr.get('created_at'):
                    dates.append(datetime.fromisoformat(pr['created_at'].replace('Z', '+00:00')))
            for event in events:
                if event.get('date'):
                    try:
                        dates.append(datetime.fromisoformat(event['date']))
                    except:
                        pass
            
            start_date = min(dates) if dates else None
            end_date = max(dates) if dates else None
            
            # Determine quarter
            quarter = None
            if start_date:
                q_num = (start_date.month - 1) // 3 + 1
                quarter = f"Q{q_num} {start_date.year}"
            
            # Generate description
            description = self._generate_description(prs, events, project_name)
            
            # Collect links
            github_links = [{'text': pr.get('title', ''), 'url': pr.get('url', ''), 'date': pr.get('created_at', '')[:10]} 
                          for pr in prs if pr.get('url')]
            calendar_links = [{'text': event.get('title', ''), 'url': '#', 'date': event.get('date', '')[:10]} 
                            for event in events if event.get('title')]
            
            merged[project_name] = {
                'name': project_name,
                'category': category,
                'icon_class': self._get_icon_class(category),
                'icon_emoji': self._get_icon_emoji(category),
                'start_date': start_date.isoformat() if start_date else None,
                'end_date': end_date.isoformat() if end_date else None,
                'quarter': quarter,
                'description': description,
                'prs': prs,
                'events': events,
                'github_links': github_links,
                'calendar_links': calendar_links,
                'tags': list(keywords) if keywords else [category]
            }
        
        return merged
    
    def _generate_description(self, prs: List[Dict], events: List[Dict], project_name: str) -> str:
        """Generate project description from PRs and events."""
        descriptions = []
        
        # Get descriptions from PR titles
        pr_titles = [pr.get('title', '') for pr in prs[:5]]
        if pr_titles:
            # Use first meaningful PR title
            for title in pr_titles:
                if len(title) > 20:
                    descriptions.append(title)
                    break
        
        # Get descriptions from event titles
        event_titles = [e.get('title', '') for e in events[:3]]
        for title in event_titles:
            if len(title) > 15 and title not in descriptions:
                descriptions.append(title)
        
        if descriptions:
            # Combine into a coherent description
            main_desc = descriptions[0]
            if len(main_desc) > 100:
                main_desc = main_desc[:97] + "..."
            return main_desc
        
        # Fallback
        keywords = self._extract_keywords(project_name)
        if keywords:
            return f"{project_name} initiative focusing on {', '.join(list(keywords)[:2])}."
        
        return f"{project_name} project work throughout the year."
    
    def organize_by_quarter(self, projects: Dict[str, Dict]) -> Dict[str, List[Dict]]:
        """Organize projects by quarter."""
        quarters = {
            f"Q1 {2025}": [],
            f"Q2 {2025}": [],
            f"Q3 {2025}": [],
            f"Q4 {2025}": []
        }
        
        for project in projects.values():
            quarter = project.get('quarter')
            if quarter and quarter in quarters:
                quarters[quarter].append(project)
            else:
                # Try to infer quarter from dates
                if project.get('start_date'):
                    try:
                        dt = datetime.fromisoformat(project['start_date'])
                        q_num = (dt.month - 1) // 3 + 1
                        q_key = f"Q{q_num} {dt.year}"
                        if q_key in quarters:
                            quarters[q_key].append(project)
                            continue
                    except:
                        pass
                # Default to Q1 if can't determine
                quarters[f"Q1 {2025}"].append(project)
        
        # Sort projects within each quarter by start date
        for quarter in quarters:
            quarters[quarter].sort(key=lambda p: p.get('start_date', ''))
        
        return quarters


if __name__ == "__main__":
    import json
    from pathlib import Path
    
    # Load config
    config_path = Path(__file__).parent.parent / "config" / "team_config.json"
    with open(config_path) as f:
        config = json.load(f)
    
    analyzer = ProjectAnalyzer(config.get('project_keywords', {}))
    
    # Test data
    test_prs = [
        {'title': 'RBAC V2 Implementation', 'body': 'Role-based access control', 'created_at': '2025-01-15T10:00:00Z', 'url': 'https://github.com/test/pr/1'},
        {'title': 'Helm Drift Detection', 'body': 'Helm comparison capabilities', 'created_at': '2025-02-20T10:00:00Z', 'url': 'https://github.com/test/pr/2'}
    ]
    
    test_events = [
        {'title': 'RBAC kickoff meeting', 'date': '2025-01-10'},
        {'title': 'Helm sync', 'date': '2025-02-18'}
    ]
    
    pr_projects = analyzer.analyze_prs(test_prs)
    event_projects = analyzer.analyze_calendar_events(test_events)
    merged = analyzer.merge_projects(pr_projects, event_projects)
    quarters = analyzer.organize_by_quarter(merged)
    
    print(json.dumps(quarters, indent=2, default=str))

