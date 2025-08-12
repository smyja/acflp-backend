import {
  Button,
  Container,
  EmptyState,
  Heading,
  HStack,
  Spinner,
  Text,
  useDisclosure,
  VStack,
} from "@chakra-ui/react";
import { createFileRoute } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { FiSearch } from "react-icons/fi";

import { TasksService } from "../../client";
import BulkUploadModal from "../../components/Tasks/BulkUploadModal";
import TasksTable from "../../components/Tasks/TasksTable.tsx";
import useAuth from "../../hooks/useAuth.ts";

export const Route = createFileRoute("/_layout/tasks")({
  component: Tasks,
});

function Tasks() {
  const { user } = useAuth();
  const {
    data: tasks,
    isLoading,
    isError,
    error,
  } = useQuery({
    queryKey: ["tasks"],
    queryFn: () => TasksService.readTasks({}),
  });
  const { open, onOpen, onClose } = useDisclosure();

  return (
    <Container maxW="full">
      <HStack justify="space-between" pt={12}>
        <Heading size="lg">Tasks Management</Heading>
        {user?.is_superuser && (
          <Button colorScheme="blue" onClick={onOpen}>
            Bulk Upload
          </Button>
        )}
      </HStack>
      {user?.is_superuser && (
        <BulkUploadModal isOpen={open} onClose={onClose} />
      )}
      {isLoading ? (
        <Spinner />
      ) : isError ? (
        <Text>Error: {error.message}</Text>
      ) : tasks && tasks.data.length > 0 ? (
        <TasksTable tasks={tasks} />
      ) : (
        <EmptyState.Root>
          <EmptyState.Content>
            <EmptyState.Indicator>
              <FiSearch />
            </EmptyState.Indicator>
            <VStack textAlign="center">
              <EmptyState.Title>No tasks available</EmptyState.Title>
              <EmptyState.Description>
                There are currently no tasks to work on. Check back later!
              </EmptyState.Description>
            </VStack>
          </EmptyState.Content>
        </EmptyState.Root>
      )}
    </Container>
  );
}