"""
Summarizer Agent - Creates concise summaries from research data
Uses Ollama with local LLM for summarization
"""

import logging
import json
from typing import Dict, Any
import ollama

logger = logging.getLogger(__name__)

class SummarizerAgent:
    """
    Summarizer Agent responsible for:
    - Creating research overviews
    - Condensing information from multiple sources
    - Extracting key insights
    """
    
    def __init__(self, model: str = "mistral"):
        """
        Initialize summarizer with Ollama model
        
        Args:
            model: Ollama model name (mistral, llama2, llama3, etc.)
        """
        self.model = model
        self._check_ollama()
        
    def _check_ollama(self):
        """Check if Ollama is available"""
        try:
            ollama.list()
            logger.info(f"Ollama connected successfully, using model: {self.model}")
        except Exception as e:
            logger.error(f"Ollama connection failed: {str(e)}")
            logger.warning("Please ensure Ollama is installed and running")
            logger.warning("Installation: https://ollama.ai/")
            logger.warning(f"Then run: ollama pull {self.model}")
    
    def summarize(self, topic: str, research_data: Dict[str, Any]) -> str:
        """
        Generate research summary using LLM
        
        Args:
            topic: Research topic
            research_data: Data from Research Agent
            
        Returns:
            Concise research summary
        """
        try:
            # Prepare context from research data
            context = self._prepare_context(topic, research_data)
            
            # Create prompt for LLM
            prompt = self._create_summary_prompt(topic, context)
            
            # Get summary from Ollama
            response = ollama.generate(model=self.model, prompt=prompt)
            summary = response['response'].strip()
            
            logger.info("Summary generated successfully")
            return summary
            
        except Exception as e:
            logger.error(f"Summarization error: {str(e)}")
            # Fallback to simple summarization without LLM
            return self._fallback_summary(topic, research_data)
    
    def _prepare_context(self, topic: str, research_data: Dict[str, Any]) -> str:
        """Prepare context from research data for LLM"""
        context_parts = []
        
        # Add Wikipedia summary if available
        if research_data.get('wikipedia_summary'):
            wiki = research_data['wikipedia_summary']
            context_parts.append(f"Wikipedia Overview: {wiki.get('extract', '')[:1000]}")
        
        # Add academic papers
        papers = research_data.get('papers', [])
        if papers:
            context_parts.append(f"\nAcademic Papers Found: {len(papers)}")
            for i, paper in enumerate(papers[:3], 1):  # Limit to top 3 papers
                context_parts.append(f"\nPaper {i}: {paper.get('title', 'N/A')}")
                context_parts.append(f"Abstract: {paper.get('summary', 'N/A')[:300]}")
        
        return "\n".join(context_parts)
    
    def _create_summary_prompt(self, topic: str, context: str) -> str:
        """Create prompt for LLM summarization"""
        prompt = f"""You are an expert research summarizer. Create a comprehensive yet concise research summary about "{topic}".

Based on the following research data, provide a well-structured summary:

{context}

Your summary should:
1. Start with a clear overview of the topic
2. Include key findings and important concepts
3. Highlight major research directions or applications
4. Be 2-3 paragraphs long
5. Use clear, academic but accessible language

Provide only the summary, no additional commentary or formatting."""
        
        return prompt
    
    def _fallback_summary(self, topic: str, research_data: Dict[str, Any]) -> str:
        """Simple fallback summarization without LLM"""
        summary_parts = [
            f"Research Summary: {topic}",
            "\nKey Findings:"
        ]
        
        # Use Wikipedia if available
        if research_data.get('wikipedia_summary'):
            wiki = research_data['wikipedia_summary']
            summary_parts.append(f"\nOverview: {wiki.get('extract', '')[:500]}")
        
        # Use paper abstracts
        papers = research_data.get('papers', [])
        if papers:
            summary_parts.append(f"\nAcademic Research ({len(papers)} papers found):")
            for paper in papers[:2]:
                summary_parts.append(f"\n• {paper.get('title', 'N/A')}")
                summary_parts.append(f"  {paper.get('summary', '')[:200]}")
        
        summary_parts.append("\nNote: This is an automated summary without LLM enhancement.")
        
        return "\n".join(summary_parts)