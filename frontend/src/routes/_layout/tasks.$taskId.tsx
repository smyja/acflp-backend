import {
  Box,
  Container,
  Heading,
  HStack,
  Spinner,
  Stack,
  Text,
} from "@chakra-ui/react";
import { createFileRoute, Link } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { FiArrowLeft } from "react-icons/fi";

import { Button } from "../../components/ui/button";
import { TasksService } from "../../client";

export const Route = createFileRoute("/_layout/tasks/$taskId")({
  component: TaskDetail,
});

function TaskDetail() {
  const { taskId } = Route.useParams();
  
  // Debug logging
  console.log("TaskDetail component rendered with taskId:", taskId);
  
  const {
    data: task,
    isLoading,
    isError,
    error,
  } = useQuery({
    queryKey: ["task", taskId],
    queryFn: () => {
      console.log("Making API call for taskId:", taskId);
      return TasksService.readTask({ taskId });
    },
  });

  if (isLoading) {
    return (
      <Container maxW="full">
        <Spinner />
      </Container>
    );
  }

  if (isError) {
    return (
      <Container maxW="full">
        <Stack gap={4} alignItems="start">
          <Link to="/tasks">
            <Button variant="ghost">
              <FiArrowLeft /> Back to Tasks
            </Button>
          </Link>
          <Text color="red.500">Error: {error?.message || "Failed to load task"}</Text>
        </Stack>
      </Container>
    );
  }

  if (!task) {
    return (
      <Container maxW="full">
        <Stack gap={4} alignItems="start">
          <Link to="/tasks">
            <Button variant="ghost">
              <FiArrowLeft /> Back to Tasks
            </Button>
          </Link>
          <Text>Task not found</Text>
        </Stack>
      </Container>
    );
  }

  return (
    <Container maxW="full">
      <Stack gap={6} alignItems="start">
        <Link to="/tasks">
          <Button variant="ghost">
            <FiArrowLeft /> Back to Tasks
          </Button>
        </Link>
        
        <Box>
          <Heading size="lg" mb={4}>
            {task.title}
          </Heading>
          
          <Stack gap={4} alignItems="start">
            <HStack>
              <Text fontWeight="bold">Type:</Text>
              <Text>{task.task_type}</Text>
            </HStack>
            
            <HStack>
              <Text fontWeight="bold">Source Language:</Text>
              <Text>{task.source_language}</Text>
            </HStack>
            
            {task.target_language && (
              <HStack>
                <Text fontWeight="bold">Target Language:</Text>
                <Text>{task.target_language}</Text>
              </HStack>
            )}
            
            <HStack>
              <Text fontWeight="bold">Reward:</Text>
              <Text>{task.reward_amount}</Text>
            </HStack>
            
            <HStack>
              <Text fontWeight="bold">Status:</Text>
              <Text>{task.status}</Text>
            </HStack>
            
            <HStack>
              <Text fontWeight="bold">Submissions:</Text>
              <Text>{task.submission_count || 0}</Text>
            </HStack>
            
            {task.description && (
              <Box>
                <Text fontWeight="bold">Description:</Text>
                <Text mt={2}>{task.description}</Text>
              </Box>
            )}
            
            <Box>
              <Text fontWeight="bold">Content:</Text>
              <Box mt={2} p={4} bg="gray.50" borderRadius="md">
                <Text>{task.content}</Text>
              </Box>
            </Box>
          </Stack>
        </Box>
      </Stack>
    </Container>
  );
}