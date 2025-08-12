import { Link as RouterLink } from "@tanstack/react-router";

import type { TasksPublic } from "../../client";
import {
  Table
} from "@chakra-ui/react";

interface TasksTableProps {
  tasks: TasksPublic;
}

const TasksTable = ({ tasks }: TasksTableProps) => {
  return (
    <Table.Root size={{ base: "sm", md: "md" }}>
      <Table.Header>
        <Table.Row>
          <Table.ColumnHeader>Title</Table.ColumnHeader>
          <Table.ColumnHeader>Type</Table.ColumnHeader>
          <Table.ColumnHeader>Source Language</Table.ColumnHeader>
          <Table.ColumnHeader>Target Language</Table.ColumnHeader>
          <Table.ColumnHeader>Reward</Table.ColumnHeader>
        </Table.Row>
      </Table.Header>
      <Table.Body>
        {tasks.data.map((task) => (
          <Table.Row key={task.id}>
            <Table.Cell>
              <RouterLink to={`/tasks/${task.id}`}>
                {task.title}
              </RouterLink>
            </Table.Cell>
            <Table.Cell>{task.task_type}</Table.Cell>
            <Table.Cell>{task.source_language}</Table.Cell>
            <Table.Cell>{task.target_language}</Table.Cell>
            <Table.Cell>{task.reward_amount}</Table.Cell>
          </Table.Row>
        ))}
      </Table.Body>
    </Table.Root>
  );
};

export default TasksTable;