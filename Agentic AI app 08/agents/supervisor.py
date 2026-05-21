"""
Supervisor Agent - Orchestrates the multi-agent workflow
Coordinates all agents and manages the research pipeline
"""

import logging
from typing import Dict, Any
from .research_agent import ResearchAgent
from .summarizer_agent import SummarizerAgent
from .reviewer_agent import ReviewerAgent

logger = logging.getLogger(__name__)

class SupervisorAgent:
    """
    Central Supervisor Agent that controls the entire workflow:
    1. Receives user query
    2. Assigns tasks to specialized agents
    3. Combines outputs
    4. Returns final response
    """
    
    def __init__(self):
        """Initialize supervisor with all specialized agents"""
        logger.info("Initializing Supervisor Agent")
        self.research_agent = ResearchAgent()
        self.summarizer_agent = SummarizerAgent()
        self.reviewer_agent = ReviewerAgent()
        self.workflow_log = []
    
    def log_step(self, step: str, agent: str, data: Any = None):
        """Log workflow steps for transparency"""
        log_entry = {
            'step': step,
            'agent': agent,
            'timestamp': logging.INFO
        }
        if data:
            log_entry['data_preview'] = str(data)[:200]
        
        self.workflow_log.append(log_entry)
        logger.info(f"[{agent}] {step}")
    
    def process_query(self, topic: str) -> Dict[str, Any]:
        """
        Main orchestration method
        Executes the complete multi-agent workflow
        
        Args:
            topic: Research topic from user
            
        Returns:
            Dictionary containing final research summary
        """
        try:
            # Step 1: Research Phase
            self.log_step("Starting research phase", "Supervisor")
            research_data = self.research_agent.fetch_research(topic)
            self.log_step("Research completed", "ResearchAgent", research_data)
            
            # Step 2: Summarization Phase
            self.log_step("Starting summarization phase", "Supervisor")
            summary = self.summarizer_agent.summarize(topic, research_data)
            self.log_step("Summarization completed", "SummarizerAgent", summary)
            
            # Step 3: Review Phase
            self.log_step("Starting review phase", "Supervisor")
            final_response = self.reviewer_agent.review_and_improve(topic, summary, research_data)
            self.log_step("Review completed", "ReviewerAgent")
            
            # Step 4: Prepare final output
            result = {
                'topic': topic,
                'research_summary': final_response,
                'sources': research_data.get('sources', []),
                'workflow_log': self.workflow_log,
                'metadata': {
                    'total_sources': len(research_data.get('sources', [])),
                    'agents_executed': ['Research', 'Summarizer', 'Reviewer']
                }
            }
            
            return result
            
        except Exception as e:
            logger.error(f"Workflow execution error: {str(e)}")
            raise
    
    def get_workflow_visualization(self) -> str:
        """Generate workflow visualization for logging"""
        steps = []
        for log in self.workflow_log:
            steps.append(f"→ {log['agent']}: {log['step']}")
        return "\n".join(steps)