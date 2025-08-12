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
  Grid,
  GridItem,
  Stack,
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
  const [fieldMappings, setFieldMappings] = useState({
    contentField: "",
    titleField: "",
    sourceLanguageField: "",
    targetLanguageField: "",
  });
  const [defaultValues, setDefaultValues] = useState({
    defaultSourceLanguage: "english",
    defaultTargetLanguage: "bini",
    defaultTaskType: "text_translation",
    defaultRewardAmount: 10,
  });
  const queryClient = useQueryClient();

  const uploadMutation = useMutation({
    mutationFn: async (data: { file: File; mappings: any; defaults: any }) => {
      return TasksService.flexibleBulkImportFromJsonl({
        formData: { file: data.file },
        contentField: data.mappings.contentField,
        titleField: data.mappings.titleField || undefined,
        sourceLanguageField: data.mappings.sourceLanguageField || undefined,
        targetLanguageField: data.mappings.targetLanguageField || undefined,
        defaultSourceLanguage: data.defaults.defaultSourceLanguage,
        defaultTargetLanguage: data.defaults.defaultTargetLanguage,
        defaultTaskType: data.defaults.defaultTaskType,
        defaultRewardAmount: data.defaults.defaultRewardAmount,
      });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["tasks"] });
      onClose();
      setSelectedFile(null);
      setFieldMappings({ contentField: "", titleField: "", sourceLanguageField: "", targetLanguageField: "" });
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
    if (selectedFile && fieldMappings.contentField) {
      uploadMutation.mutate({
        file: selectedFile,
        mappings: fieldMappings,
        defaults: defaultValues,
      });
    }
  };

  const updateFieldMapping = (field: string, value: string) => {
    setFieldMappings(prev => ({ ...prev, [field]: value }));
  };

  const updateDefaultValue = (field: string, value: string | number) => {
    setDefaultValues(prev => ({ ...prev, [field]: value }));
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
          <VStack gap={6}>
            <Text fontSize="sm" color="gray.600">
              Upload a JSONL file and map its fields to task properties. Perfect for Hugging Face datasets!
            </Text>

            <Box
              border="2px dashed"
              borderColor="gray.300"
              borderRadius="md"
              p={6}
              textAlign="center"
              _hover={{ borderColor: "blue.400" }}
              w="full"
            >
              <VStack>
                <FiUpload size={24} />
                <Text>Upload a JSONL file</Text>
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

            <Box w="full">
              <Text fontWeight="bold" mb={3}>Field Mapping</Text>
              <Grid templateColumns="repeat(2, 1fr)" gap={4}>
                <GridItem>
                  <Stack gap={1}>
                    <Text fontSize="sm" fontWeight="medium">Content Field *</Text>
                    <Input
                      placeholder="e.g., text, content, translation.en"
                      value={fieldMappings.contentField}
                      onChange={(e) => updateFieldMapping('contentField', e.target.value)}
                    />
                    <Text fontSize="xs" color="gray.600">JSONL key containing text to translate</Text>
                  </Stack>
                </GridItem>

                <GridItem>
                  <Stack gap={1}>
                    <Text fontSize="sm" fontWeight="medium">Title Field</Text>
                    <Input
                      placeholder="e.g., id, title, name"
                      value={fieldMappings.titleField}
                      onChange={(e) => updateFieldMapping('titleField', e.target.value)}
                    />
                    <Text fontSize="xs" color="gray.600">Optional: Field for task title</Text>
                  </Stack>
                </GridItem>

                <GridItem>
                  <Stack gap={1}>
                    <Text fontSize="sm" fontWeight="medium">Source Language Field</Text>
                    <Input
                      placeholder="e.g., source_lang, from"
                      value={fieldMappings.sourceLanguageField}
                      onChange={(e) => updateFieldMapping('sourceLanguageField', e.target.value)}
                    />
                    <Text fontSize="xs" color="gray.600">Optional: Field for source language</Text>
                  </Stack>
                </GridItem>

                <GridItem>
                  <Stack gap={1}>
                    <Text fontSize="sm" fontWeight="medium">Target Language Field</Text>
                    <Input
                      placeholder="e.g., target_lang, to"
                      value={fieldMappings.targetLanguageField}
                      onChange={(e) => updateFieldMapping('targetLanguageField', e.target.value)}
                    />
                    <Text fontSize="xs" color="gray.600">Optional: Field for target language</Text>
                  </Stack>
                </GridItem>
              </Grid>
            </Box>

            <Box w="full">
              <Text fontWeight="bold" mb={3}>Default Values</Text>
              <Grid templateColumns="repeat(2, 1fr)" gap={4}>
                <GridItem>
                  <Stack gap={1}>
                    <Text fontSize="sm" fontWeight="medium">Default Source Language</Text>
                    <Input
                      value={defaultValues.defaultSourceLanguage}
                      onChange={(e) => updateDefaultValue('defaultSourceLanguage', e.target.value)}
                    />
                  </Stack>
                </GridItem>

                <GridItem>
                  <Stack gap={1}>
                    <Text fontSize="sm" fontWeight="medium">Default Target Language</Text>
                    <Input
                      value={defaultValues.defaultTargetLanguage}
                      onChange={(e) => updateDefaultValue('defaultTargetLanguage', e.target.value)}
                    />
                  </Stack>
                </GridItem>

                <GridItem>
                  <Stack gap={1}>
                    <Text fontSize="sm" fontWeight="medium">Default Task Type</Text>
                    <Input
                      value={defaultValues.defaultTaskType}
                      onChange={(e) => updateDefaultValue('defaultTaskType', e.target.value)}
                    />
                  </Stack>
                </GridItem>

                <GridItem>
                  <Stack gap={1}>
                    <Text fontSize="sm" fontWeight="medium">Default Reward Amount</Text>
                    <Input
                      type="number"
                      step="0.01"
                      value={defaultValues.defaultRewardAmount}
                      onChange={(e) => updateDefaultValue('defaultRewardAmount', parseFloat(e.target.value) || 0)}
                    />
                  </Stack>
                </GridItem>
              </Grid>
            </Box>

            <Box w="full" bg="blue.50" p={4} borderRadius="md">
              <Text fontSize="sm" fontWeight="bold" mb={2}>Example for your Hugging Face format:</Text>
              <Text fontSize="xs" fontFamily="mono" mb={2}>
                {`{"translation": {"ffen": "Where is the market?", "bini": ""}, "id": "location_001"}`}
              </Text>
              <Text fontSize="xs">
                Content Field: <strong>translation.ffen</strong> | Title Field: <strong>id</strong>
              </Text>
              <Text fontSize="xs" mt={2} color="orange.600">
                Note: Use "translation.ffen" (not just "ffen") to access nested fields!
              </Text>
            </Box>
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
              disabled={!selectedFile || !fieldMappings.contentField || uploadMutation.isPending}
              loading={uploadMutation.isPending}
            >
              Import Tasks
            </Button>
          </HStack>
        </DialogFooter>
        <DialogCloseTrigger />
      </DialogContent>
    </DialogRoot>
  );
};

export default BulkUploadModal;