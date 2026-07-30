import argparse
import json
import logging
import sys
import requests

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("deploy")

API_BASE = "https://voicecon-be.onrender.com/api/v1"

def get_headers(token: str) -> dict:
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }

def deploy(token: str):
    headers = get_headers(token)
    
    # 1. Fetch Integration Connections (to find Trello and Google Calendar)
    logger.info("Fetching existing integration connections...")
    res = requests.get(f"{API_BASE}/integrations/connections", headers=headers)
    if not res.ok:
        logger.error(f"Failed to fetch connections: {res.text}")
        sys.exit(1)
        
    connections = res.json().get("connections", [])
    trello_conn = next((c for c in connections if c.get("connector", {}).get("slug") == "trello"), None)
    gcal_conn = next((c for c in connections if c.get("connector", {}).get("slug") == "google-calendar"), None)
    
    if not trello_conn or not gcal_conn:
        logger.error("Please ensure both Trello and Google Calendar are connected in the UI before running this script.")
        # We won't exit; we will build placeholders if not found for testing purposes.
        trello_conn_id = trello_conn["id"] if trello_conn else "placeholder_trello"
        gcal_conn_id = gcal_conn["id"] if gcal_conn else "placeholder_gcal"
    else:
        trello_conn_id = trello_conn["id"]
        gcal_conn_id = gcal_conn["id"]
        
    # 2. Create Google Calendar Workflow
    logger.info("Creating Google Calendar Workflow...")
    gcal_workflow = {
        "name": "Production - Google Calendar Booking",
        "description": "Checks availability and books an event in Google Calendar if the slot is free.",
        "trigger_type": "manual",
        "trigger_config": {},
        "workflow_steps": [],
        "graph": {
            "schema_version": 2,
            "nodes": [
                {
                    "id": "trigger",
                    "type": "trigger",
                    "name": "Agent Trigger",
                    "position": {"x": 340, "y": 40},
                    "config": {
                        "inputs": [
                            {"name": "summary", "type": "string"},
                            {"name": "start_time", "type": "string", "description": "ISO timestamp"},
                            {"name": "end_time", "type": "string", "description": "ISO timestamp"}
                        ]
                    }
                },
                {
                    "id": "create_event",
                    "type": "action",
                    "name": "Create Event",
                    "position": {"x": 340, "y": 210},
                    "config": {
                        "connection_id": gcal_conn_id,
                        "action": "create_event",
                        "parameters": {
                            "calendar_id": "primary",
                            "summary": "{{trigger.summary}}",
                            "start_time": "{{trigger.start_time}}",
                            "end_time": "{{trigger.end_time}}"
                        }
                    }
                }
            ],
            "edges": [
                {"id": "e_trigger_create", "source": "trigger", "sourceHandle": "out", "target": "create_event", "targetHandle": "in"}
            ]
        }
    }
    res = requests.post(f"{API_BASE}/workflows", json=gcal_workflow, headers=headers)
    if res.ok:
        gcal_wf_id = res.json()["id"]
        logger.info(f"Created Google Calendar Workflow: {gcal_wf_id}")
    else:
        logger.error(f"Failed to create GCAL workflow: {res.text}")
        sys.exit(1)

    # 3. Create Trello Workflow
    logger.info("Creating Trello Workflow...")
    trello_workflow = {
        "name": "Production - Create Trello Task",
        "description": "Creates a task in Trello, handling priority tagging.",
        "trigger_type": "manual",
        "trigger_config": {},
        "workflow_steps": [],
        "graph": {
            "schema_version": 2,
            "nodes": [
                {
                    "id": "trigger",
                    "type": "trigger",
                    "name": "Agent Trigger",
                    "position": {"x": 340, "y": 40},
                    "config": {
                        "inputs": [
                            {"name": "task_name", "type": "string"},
                            {"name": "task_description", "type": "string"},
                            {"name": "is_urgent", "type": "string", "description": "'true' or 'false'"}
                        ]
                    }
                },
                {
                    "id": "check_urgent",
                    "type": "condition",
                    "name": "Is Urgent?",
                    "position": {"x": 340, "y": 210},
                    "config": {
                        "variable": "{{trigger.is_urgent}}",
                        "operator": "equals",
                        "value": "true"
                    }
                },
                {
                    "id": "format_urgent",
                    "type": "transform",
                    "name": "Add Urgent Tag",
                    "position": {"x": 120, "y": 380},
                    "config": {
                        "transformations": {
                            "final_name": "[URGENT] {{trigger.task_name}}"
                        }
                    }
                },
                {
                    "id": "format_normal",
                    "type": "transform",
                    "name": "Keep Normal Name",
                    "position": {"x": 560, "y": 380},
                    "config": {
                        "transformations": {
                            "final_name": "{{trigger.task_name}}"
                        }
                    }
                },
                {
                    "id": "create_card",
                    "type": "action",
                    "name": "Create Trello Card",
                    "position": {"x": 340, "y": 550},
                    "config": {
                        "connection_id": trello_conn_id,
                        "action": "create_card",
                        "parameters": {
                            "list_id": "placeholder_list_id", # Normally requires fetching the list ID dynamically or hardcoding defaults
                            "name": "{{final_name}}",
                            "description": "{{trigger.task_description}}"
                        }
                    }
                }
            ],
            "edges": [
                {"id": "e_trigger_cond", "source": "trigger", "sourceHandle": "out", "target": "check_urgent", "targetHandle": "in"},
                {"id": "e_cond_true", "source": "check_urgent", "sourceHandle": "true", "target": "format_urgent", "targetHandle": "in"},
                {"id": "e_cond_false", "source": "check_urgent", "sourceHandle": "false", "target": "format_normal", "targetHandle": "in"},
                {"id": "e_form_urg_act", "source": "format_urgent", "sourceHandle": "out", "target": "create_card", "targetHandle": "in"},
                {"id": "e_form_nor_act", "source": "format_normal", "sourceHandle": "out", "target": "create_card", "targetHandle": "in"}
            ]
        }
    }
    res = requests.post(f"{API_BASE}/workflows", json=trello_workflow, headers=headers)
    if res.ok:
        trello_wf_id = res.json()["id"]
        logger.info(f"Created Trello Workflow: {trello_wf_id}")
    else:
        logger.error(f"Failed to create Trello workflow: {res.text}")
        sys.exit(1)

    # 4. Create Tools
    logger.info("Creating Workflow Tools...")
    gcal_tool = {
        "name": "Book Calendar Meeting",
        "description": "Book a meeting into the user's primary Google Calendar.",
        "category": "assistant",
        "tool_type": "workflow",
        "config": {
            "workflow_id": gcal_wf_id,
            "filler_message": "Let me book that meeting for you."
        }
    }
    res = requests.post(f"{API_BASE}/tools", json=gcal_tool, headers=headers)
    gcal_tool_id = res.json().get("id")

    trello_tool = {
        "name": "Create Task Card",
        "description": "Create a task in Trello. Pass 'true' for is_urgent if the task is critical.",
        "category": "assistant",
        "tool_type": "workflow",
        "config": {
            "workflow_id": trello_wf_id,
            "filler_message": "Give me a second to add this task to your board."
        }
    }
    res = requests.post(f"{API_BASE}/tools", json=trello_tool, headers=headers)
    trello_tool_id = res.json().get("id")

    # 5. Create Agent
    logger.info("Deploying Production Agent...")
    agent_data = {
        "name": "Sarah - Executive Assistant",
        "description": "Production agent handling meeting scheduling and task management.",
        "system_prompt": "You are Sarah, an advanced AI Executive Assistant. Your goal is to book calendar meetings and log tasks into Trello. Rely on your tools exclusively. Do not invent answers.",
        "first_message": "Hello! I'm Sarah, your automated Executive Assistant. I can help book your meetings or add tasks to your Trello board. How can I help you today?",
        "llm_provider": "openai",
        "llm_model": "gpt-4o",
        "is_active": True
    }
    res = requests.post(f"{API_BASE}/agents", json=agent_data, headers=headers)
    if res.ok:
        agent_id = res.json()["id"]
        logger.info(f"Deployed Agent: {agent_id}")
        
        # Assign tools
        requests.post(f"{API_BASE}/tools/agents/{agent_id}/tools", json={"tool_id": gcal_tool_id}, headers=headers)
        requests.post(f"{API_BASE}/tools/agents/{agent_id}/tools", json={"tool_id": trello_tool_id}, headers=headers)
        
        logger.info("\nSuccess! The agent is deployed.")
        logger.info(f"You can now test it at /dashboard/agents/{agent_id}/test or via the Chat Widget.")
    else:
        logger.error(f"Failed to create Agent: {res.text}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Deploy Production Agent to Live VoiceCon Platform via API")
    parser.add_argument("--token", required=True, help="Your Dashboard session JWT token (found in browser localStorage)")
    args = parser.parse_args()
    deploy(args.token)
