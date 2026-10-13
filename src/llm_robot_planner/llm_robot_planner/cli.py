import sys

import rclpy

from .executor import PlanExecutor
from .llm_client import LLMPlannerClient
from .validator import PlanValidationError


def run_interactive_planner(
    args=None, input_func=input, print_func=print, llm_client=None, executor=None
):
    """
    Run the interactive loop for the LLM task planner.

    Can be injected with custom input/print functions and clients for testing.
    """
    print_func('\n' + '=' * 55)
    print_func('     LLM Autonomous Task Planner (ROS 2 / Nav2)     ')
    print_func('=' * 55)

    # Prompt user for natural language task
    try:
        prompt_msg = "\nEnter your natural-language task (or 'exit' to quit): "
        task_prompt = input_func(prompt_msg).strip()
    except (KeyboardInterrupt, EOFError):
        print_func('\n[INFO] Session interrupted by user.')
        return 0

    if not task_prompt or task_prompt.lower() in {'exit', 'quit', 'q'}:
        print_func('[INFO] Exiting task planner.')
        return 0

    if llm_client is None:
        try:
            llm_client = LLMPlannerClient()
        except Exception as e:
            print_func(f'[ERROR] Failed to initialize LLM client: {e}')
            return 1

    print_func('\n[INFO] Generating and validating plan with Gemini...')
    try:
        plan = llm_client.generate_plan(task_prompt)
    except PlanValidationError as e:
        print_func(f'[ERROR] Plan generation/validation failed: {e}')
        return 1
    except Exception as e:
        print_func(f'[ERROR] Unexpected error: {e}')
        return 1

    # Display the plan for user review
    print_func('\n' + '-' * 45)
    print_func('             PROPOSED PLAN')
    print_func('-' * 45)
    for idx, step in enumerate(plan, start=1):
        print_func(f"  Step {idx}: {step['action']} -> target: '{step['target']}'")
    print_func('-' * 45)

    # Human-in-the-loop explicit confirmation
    try:
        confirm_msg = '\nDo you want the robot to execute this plan? [y/N]: '
        confirm = input_func(confirm_msg).strip().lower()
    except (KeyboardInterrupt, EOFError):
        print_func('\n[INFO] Plan execution canceled.')
        return 0

    if confirm not in {'y', 'yes'}:
        print_func('[INFO] Plan rejected by user. No robot movement initiated.')
        return 0

    # Execute plan through ROS 2 executor
    print_func('\n[INFO] Plan approved! Initializing ROS 2 executor...')
    created_local_executor = False
    if executor is None:
        if not rclpy.ok():
            rclpy.init(args=args)
        executor = PlanExecutor()
        created_local_executor = True

    try:
        success = executor.execute_plan(plan)
        if success:
            print_func('\n[SUCCESS] All plan steps executed successfully!')
            return 0
        elif getattr(executor, '_interrupted', False) is True:
            print_func('\n[INFO] Execution interrupted by user.')
            return 0
        else:
            err_msg = '\n[FAILURE] Plan execution halted due to navigation error or cancellation.'
            print_func(err_msg)
            return 1
    except (KeyboardInterrupt, EOFError):
        if executor and getattr(executor, '_current_goal_handle', None):
            executor.cancel_active_goal(executor._current_goal_handle)
        print_func('\n[INFO] Execution interrupted by user.')
        return 0
    finally:
        if created_local_executor:
            executor.destroy_node()
            if rclpy.ok():
                rclpy.shutdown()


def main(args=None):
    sys.exit(run_interactive_planner(args=args))


if __name__ == '__main__':
    main()
