import {
  Button,
  DialogActionTrigger,
  DialogBody,
  DialogCloseTrigger,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogRoot,
  DialogTitle,
  HStack,
  Text,
  VStack,
  Input,
  Box,
} from "@chakra-ui/react";
import { useState } from "react";
import { FiUpload } from "react-icons/fi";
import { TasksService } from "../../client";
import { useMutation, useQueryClient } from "@tanstack/react-query";

interface BulkUploadModalProps {
  isOpen: boolean;
  onClose: () => void;
}

const BulkUploadModal = ({ isOpen, onClose }: BulkUploadModalProps) => {
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const queryClient = useQueryClient();

  const uploadMutation = useMutation({
    mutationFn: async (file: File) => {
      const formData = new FormData();
      formData.append("file", file);
      return TasksService.bulkImportTasksFromJsonl({
        formData: formData as any,
        defaultRewardAmount: 10,
      });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["tasks"] });
      onClose();
      setSelectedFile(null);
    },
    onError: (error) => {
      console.error("Upload failed:", error);
    },
  });

  const handleFileSelect = (files: FileList | null) => {
    if (files && files.length > 0) {
      setSelectedFile(files[0]);
    }
  };

  const handleUpload = () => {
    if (selectedFile) {
      uploadMutation.mutate(selectedFile);
    }
  };

  const handleClose = () => {
    setSelectedFile(null);
    onClose();
  };

  return (
    <DialogRoot open={isOpen} onOpenChange={({ open }) => !open && handleClose()}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Bulk Upload Tasks</DialogTitle>
        </DialogHeader>
        <DialogBody>
          <VStack gap={4}>
            <Text fontSize="sm" color="gray.600">
              Upload a JSONL file with task data. Each line should contain a JSON object with task fields.
            </Text>
            <Box
              border="2px dashed"
              borderColor="gray.300"
              borderRadius="md"
              p={6}
              textAlign="center"
              _hover={{ borderColor: "blue.400" }}
            >
              <VStack>
                <FiUpload size={24} />
                <Text>Upload a JSONL file with task data</Text>
                <Input
                  type="file"
                  accept=".jsonl,.json"
                  onChange={(e) => handleFileSelect(e.target.files)}
                  variant="outline"
                />
              </VStack>
            </Box>
            {selectedFile && (
              <Text fontSize="sm" color="green.600">
                Selected: {selectedFile.name}
              </Text>
            )}
          </VStack>
        </DialogBody>
        <DialogFooter>
          <HStack>
            <DialogActionTrigger asChild>
              <Button variant="outline" onClick={handleClose}>
                Cancel
              </Button>
            </DialogActionTrigger>
            <Button
              colorScheme="blue"
              onClick={handleUpload}
              disabled={!selectedFile || uploadMutation.isPending}
              loading={uploadMutation.isPending}
            >
              Upload
            </Button>
          </HStack>
        </DialogFooter>
        <DialogCloseTrigger />
      </DialogContent>
    </DialogRoot>
  );
};

export default BulkUploadModal;