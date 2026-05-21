"""
Research Agent - Fetches information from free APIs
Uses arXiv and Wikipedia APIs to gather research data
"""

import logging
import requests
from typing import Dict, Any, List
from datetime import datetime

logger = logging.getLogger(__name__)

class ResearchAgent:
    """
    Research Agent responsible for:
    - Fetching academic papers from arXiv
    - Getting summaries from Wikipedia
    - Extracting relevant information
    """
    
    def __init__(self):
        """Initialize research agent with API endpoints"""
        self.arxiv_url = "http://export.arxiv.org/api/query"
        self.wikipedia_url = "https://en.wikipedia.org/api/rest_v1/page/summary"
        self.user_agent = "ResearchFlowLite/1.0"
        
    def fetch_research(self, topic: str) -> Dict[str, Any]:
        """
        Fetch research information from multiple sources
        
        Args:
            topic: Research topic
            
        Returns:
            Dictionary containing research data from various sources
        """
        research_data = {
            'topic': topic,
            'papers': [],
            'wikipedia_summary': None,
            'sources': [],
            'timestamp': datetime.now().isoformat()
        }
        
        try:
            # Fetch from arXiv
            arxiv_results = self._fetch_arxiv(topic)
            if arxiv_results:
                research_data['papers'] = arxiv_results
                research_data['sources'].extend([p['url'] for p in arxiv_results])
                logger.info(f"Found {len(arxiv_results)} papers from arXiv")
            
            # Fetch from Wikipedia
            wiki_result = self._fetch_wikipedia(topic)
            if wiki_result:
                research_data['wikipedia_summary'] = wiki_result
                research_data['sources'].append(wiki_result.get('source_url', ''))
                logger.info("Successfully fetched Wikipedia summary")
            
        except Exception as e:
            logger.error(f"Error fetching research data: {str(e)}")
        
        return research_data
    
    def _fetch_arxiv(self, topic: str, max_results: int = 5) -> List[Dict[str, Any]]:
        """
        Fetch papers from arXiv API
        
        Args:
            topic: Search query
            max_results: Maximum number of papers to fetch
            
        Returns:
            List of paper dictionaries
        """
        try:
            params = {
                'search_query': f'all:{topic}',
                'start': 0,
                'max_results': max_results,
                'sortBy': 'relevance',
                'sortOrder': 'descending'
            }
            
            headers = {
                'User-Agent': self.user_agent
            }
            
            response = requests.get(self.arxiv_url, params=params, headers=headers, timeout=10)
            response.raise_for_status()
            
            # Parse XML response (simplified - in production use xml.etree)
            import xml.etree.ElementTree as ET
            root = ET.fromstring(response.content)
            
            # XML namespaces
            ns = {'atom': 'http://www.w3.org/2005/Atom'}
            
            papers = []
            for entry in root.findall('atom:entry', ns)[:max_results]:
                paper = {
                    'title': entry.find('atom:title', ns).text.strip() if entry.find('atom:title', ns) is not None else 'N/A',
                    'summary': entry.find('atom:summary', ns).text.strip()[:500] if entry.find('atom:summary', ns) is not None else 'N/A',
                    'authors': [],
                    'published': entry.find('atom:published', ns).text if entry.find('atom:published', ns) is not None else 'N/A',
                    'url': entry.find('atom:id', ns).text if entry.find('atom:id', ns) is not None else '#'
                }
                
                # Extract authors
                for author in entry.findall('atom:author', ns):
                    name = author.find('atom:name', ns)
                    if name is not None and name.text:
                        paper['authors'].append(name.text)
                
                papers.append(paper)
            
            return papers
            
        except Exception as e:
            logger.error(f"arXiv API error: {str(e)}")
            return []
    
    def _fetch_wikipedia(self, topic: str) -> Dict[str, Any]:
        """
        Fetch summary from Wikipedia API
        
        Args:
            topic: Search topic
            
        Returns:
            Wikipedia summary dictionary
        """
        try:
            # Clean topic for URL
            clean_topic = topic.replace(' ', '_')
            url = f"{self.wikipedia_url}/{clean_topic}"
            
            headers = {
                'User-Agent': self.user_agent
            }
            
            response = requests.get(url, headers=headers, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                return {
                    'title': data.get('title', 'N/A'),
                    'extract': data.get('extract', 'No summary available'),
                    'source_url': f"https://en.wikipedia.org/wiki/{clean_topic}",
                    'description': data.get('description', '')
                }
            elif response.status_code == 404:
                # Try search as fallback
                return self._wikipedia_search(topic)
            else:
                logger.warning(f"Wikipedia API returned {response.status_code}")
                return None
                
        except Exception as e:
            logger.error(f"Wikipedia API error: {str(e)}")
            return None
    
    def _wikipedia_search(self, topic: str) -> Dict[str, Any]:
        """Search Wikipedia as fallback"""
        try:
            search_url = "https://en.wikipedia.org/w/api.php"
            params = {
                'action': 'query',
                'list': 'search',
                'srsearch': topic,
                'format': 'json',
                'limit': 1
            }
            
            response = requests.get(search_url, params=params, timeout=10)
            if response.status_code == 200:
                data = response.json()
                search_results = data.get('query', {}).get('search', [])
                if search_results:
                    title = search_results[0]['title']
                    # Fetch full summary for the found title
                    return self._fetch_wikipedia(title)
            
            return None
            
        except Exception as e:
            logger.error(f"Wikipedia search error: {str(e)}")
            return None