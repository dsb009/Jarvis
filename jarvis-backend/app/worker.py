"""Agent Worker - Processes tasks from Upstash queue."""
import asyncio
import json
import logging
import sys

from app.services.queue import task_queue
from app.services.llm_router import llm_router

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class AgentWorker:
    """Worker that processes agent tasks from the queue."""

    AGENT_HANDLERS = {
        "meal.plan.requested": "handle_meal_plan",
        "fitness.workout.requested": "handle_fitness",
        "finance.brief.requested": "handle_finance",
    }

    async def process_task(self, task: dict) -> dict:
        """Process a single task."""
        task_type = task.get("type", "")
        payload = task.get("payload", {})

        logger.info(f"Processing task: {task_type}")

        # Get appropriate handler
        handler_name = self.AGENT_HANDLERS.get(task_type)
        if not handler_name:
            logger.warning(f"No handler for task type: {task_type}")
            return {"status": "unknown_task_type", "task_type": task_type}

        handler = getattr(self, handler_name, None)
        if not handler:
            logger.error(f"Handler not found: {handler_name}")
            return {"status": "handler_not_found"}

        try:
            result = await handler(payload)
            return {"status": "completed", "result": result}
        except Exception as e:
            logger.exception(f"Error processing task: {e}")
            return {"status": "failed", "error": str(e)}

    async def handle_meal_plan(self, payload: dict) -> dict:
        """Generate meal plan using LLM."""
        user_id = payload.get("user_id")
        preferences = payload.get("preferences", {})

        # Use LLM router to choose model
        system = """You are Jarvis's Meal Planning Agent.
Create personalized weekly meal plans based on user preferences."""

        user = f"Create a meal plan for: {preferences.get('diet', 'balanced')}"

        response = await llm_router.call(
            task_description="meal plan",
            system=system,
            user=user
        )

        return {"meal_plan": response}

    async def handle_fitness(self, payload: dict) -> dict:
        """Generate workout plan using LLM."""
        user_id = payload.get("user_id")
        preferences = payload.get("preferences", {})

        system = """You are Jarvis's Fitness Agent.
Create personalized workout plans based on user goals."""

        user = f"Create a workout plan for: {preferences.get('goal', 'fitness')}"

        response = await llm_router.call(
            task_description="workout plan",
            system=system,
            user=user
        )

        return {"workout_plan": response}

    async def handle_finance(self, payload: dict) -> dict:
        """Generate market brief using LLM."""
        system = """You are Jarvis's Finance Agent.
Provide educational market insights. NEVER give financial advice."""

        user = "Generate today's market brief for the user's watchlist."

        response = await llm_router.call(
            task_description="market analysis",
            system=system,
            user=user
        )

        return {"market_brief": response}

    async def run(self):
        """Main worker loop."""
        logger.info("Agent Worker started")

        while True:
            try:
                # Get task from queue (blocking)
                task = await task_queue.dequeue(timeout=30)

                if task:
                    task_id = task.get("id")
                    logger.info(f"Processing task: {task_id}")

                    result = await self.process_task(task)

                    # Store result
                    if task_id:
                        await task_queue.set_task_result(task_id, result)

                    logger.info(f"Task completed: {task_id}")
                else:
                    # No task, sleep briefly
                    await asyncio.sleep(1)

            except KeyboardInterrupt:
                logger.info("Worker stopped")
                break
            except Exception as e:
                logger.exception(f"Worker error: {e}")
                await asyncio.sleep(5)


async def main():
    """Entry point for Cloud Run Job."""
    worker = AgentWorker()
    await worker.run()


if __name__ == "__main__":
    asyncio.run(main())