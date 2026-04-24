All Tools I Have Available

File Operations

- Read - Read a file (file_path, offset, limit, pages)
- Write - Write a file (file_path, content)
- Edit - Edit a file (file_path, old_string, new_string, replace_all)
- NotebookEdit - Edit a notebook cell (notebook_path, cell_id, new_source, cell_type, edit_mode)

Execution

- Bash - Run commands (command, description, timeout, run_in_background, dangerouslyDisableSandbox)

Task Management

- TaskCreate - Create tasks (subject, description, activeForm, metadata)
- TaskList - List tasks
- TaskGet - Get task (taskId)
- TaskUpdate - Update task (taskId, subject, description, activeForm, status, owner, addBlocks, addBlockedBy, metadata)
- TaskStop - Stop task (task_id, shell_id)

Monitoring

- Monitor - Monitor events (description, timeout_ms, persistent, command)

Scheduling

- ScheduleWakeup - Schedule wakeup (delaySeconds, reason, prompt)
- CronCreate - Create cron (cron, prompt, recurring, durable)
- CronList - List crons
- CronDelete - Delete cron (id)

Agents

- Agent - Launch agent (description, prompt, subagent_type, model, run_in_background)

User Interaction

- AskUserQuestion - Ask questions (questions, answers, annotations, metadata)

Web

- WebFetch - Fetch URL (url, prompt)
- WebSearch - Search (query, allowed_domains, blocked_domains)

Plan Mode

- EnterPlanMode - Enter plan mode
- ExitPlanMode - Exit plan mode (allowedPrompts)

Worktree

- EnterWorktree - Enter worktree (name, path)
- ExitWorktree - Exit worktree (action, discard_changes)

System

- RemoteTrigger - Remote trigger (action, trigger_id, body)
- Skill - Execute skill (skill, args)
- PushNotification - Notification (message, status)

That's all 42 tools.
