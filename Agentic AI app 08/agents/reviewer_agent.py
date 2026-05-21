"""
Reviewer Agent - Improves grammar, structure, and quality of final response
Validates and enhances the research output
"""

import logging
import re
from typing import Dict, Any
import ollama

logger = logging.getLogger(__name__)

class ReviewerAgent:
    """
    Reviewer Agent responsible for:
    - Improving grammar and writing quality
    - Validating response structure
    - Ensuring coherence and clarity
    - Adding citations and references
    """
    
    def __init__(self, model: str = "mistral"):
        """
        Initialize reviewer with Ollama model
        
        Args:
            model: Ollama model name
        """
        self.model = model
        
    def review_and_improve(self, topic: str, summary: str, research_data: Dict[str, Any]) -> str:
        """
        Review and improve the research summary
        
        Args:
            topic: Original research topic
            summary: Generated summary from Summarizer Agent
            research_data: Raw research data for validation
            
        Returns:
            Improved final response
        """
        try:
            # First, validate the summary
            validation = self._validate_summary(topic, summary, research_data)
            
            # Improve the summary using LLM
            improved = self._improve_with_llm(topic, summary, validation)
            
            # Add citations and final polish
            final = self._add_citations(improved, research_data)
            
            logger.info("Review and improvement completed")
            return final
            
        except Exception as e:
            logger.error(f"Review error: {str(e)}")
            # Return original summary with basic improvements
            return self._basic_improvement(summary, research_data)
    
    def _validate_summary(self, topic: str, summary: str, research_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate summary quality and completeness
        """
        validation = {
            'has_topic': topic.lower() in summary.lower(),
            'length_adequate': len(summary) > 200,
            'has_sources': len(research_data.get('sources', [])) > 0,
            'issues': []
        }
        
        # Check for common issues
        if not validation['has_topic']:
            validation['issues'].append("Topic not clearly mentioned")
        
        if not validation['length_adequate']:
            validation['issues'].append("Summary too brief")
        
        # Check for markdown or formatting issues
        if re.search(r'\*{3,}', summary):
            validation['issues'].append("Contains excessive markdown")
        
        return validation
    
    def _improve_with_llm(self, topic: str, summary: str, validation: Dict[str, Any]) -> str:
        """
        Use LLM to improve summary quality
        """
        try:
            # Create improvement prompt
            issues_text = ", ".join(validation['issues']) if validation['issues'] else "None"
            
            prompt = f"""You are an expert research reviewer. Improve the following research summary about "{topic}".

Original Summary:
{summary}

Detected Issues: {issues_text}

Your task:
1. Fix any grammar or style issues
2. Improve sentence structure and flow
3. Ensure the content is clear and logical
4. Add transitions between paragraphs
5. Maintain the original meaning and facts

Provide ONLY the improved version, no explanations or markdown formatting:

Improved Summary:"""
            
            response = ollama.generate(model=self.model, prompt=prompt)
            improved = response['response'].strip()
            
            return improved if improved else summary
            
        except Exception as e:
            logger.error(f"LLM improvement failed: {str(e)}")
            return summary
    
    def _add_citations(self, summary: str, research_data: Dict[str, Any]) -> str:
        """
        Add source citations to the summary
        """
        sources = research_data.get('sources', [])
        
        if not sources:
            return summary
        
        # Create references section
        references = "\n\n## References\n"
        for i, source in enumerate(sources[:5], 1):  # Limit to 5 sources
            if source and source != '#':
                references += f"\n{i}. {source}"
        
        # Add a note about sources in the summary if not present
        if "sources" not in summary.lower() and "references" not in summary.lower():
            summary += "\n\n*Note: This summary synthesizes information from multiple academic and reference sources.*"
        
        return summary + references
    
    def _basic_improvement(self, summary: str, research_data: Dict[str, Any]) -> str:
        """
        Basic rule-based improvements when LLM is unavailable
        """
        improved = summary
        
        # Fix common formatting issues
        improved = re.sub(r'\n{3,}', '\n\n', improved)  # Remove excessive newlines
        improved = improved.strip()
        
        # Ensure proper capitalization at start
        if improved and improved[0].islower():
            improved = improved[0].upper() + improved[1:]
        
        # Add sources if available
        sources = research_data.get('sources', [])
        if sources:
            improved += "\n\nSources: " + ", ".join(sources[:3])
        
        return improved