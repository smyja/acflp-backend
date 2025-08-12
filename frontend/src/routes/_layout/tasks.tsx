import { Button, Container, Heading, HStack, useDisclosure } from "@chakra-ui/react";
import { createFileRoute } from "@tanstack/react-router";
import useAuth from "../../hooks/useAuth.ts";
import BulkUploadModal from "../../components/Tasks/BulkUploadModal";

export const Route = createFileRoute("/_layout/tasks")({
  component: Tasks,
});

function Tasks() {
  const { user } = useAuth();
  const { open, onOpen, onClose } = useDisclosure();

  return (
    <Container maxW="full">
      <HStack justify="space-between" pt={12}>
        <Heading size="lg">Tasks Management</Heading>
        {user?.is_superuser && (
          <Button colorScheme="blue" onClick={onOpen}>Bulk Upload</Button>
        )}
      </HStack>
      {user?.is_superuser && (
        <BulkUploadModal isOpen={open} onClose={onClose} />
      )}
    </Container>
  );
}