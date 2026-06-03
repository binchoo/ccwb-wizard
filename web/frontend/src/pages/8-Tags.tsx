import { useState } from "react";
import Container from "@cloudscape-design/components/container";
import FormField from "@cloudscape-design/components/form-field";
import Input from "@cloudscape-design/components/input";
import Button from "@cloudscape-design/components/button";
import Header from "@cloudscape-design/components/header";
import SpaceBetween from "@cloudscape-design/components/space-between";
import Table from "@cloudscape-design/components/table";
import { useWizardStore } from "../store";

export default function TagsPage() {
  const { draft, updateDraft } = useWizardStore();
  const [newKey, setNewKey] = useState("");
  const [newValue, setNewValue] = useState("");

  const tags = Object.entries(draft.tags);

  const addTag = () => {
    if (newKey && !newKey.startsWith("aws:")) {
      updateDraft({ tags: { ...draft.tags, [newKey]: newValue } });
      setNewKey("");
      setNewValue("");
    }
  };

  const removeTag = (key: string) => {
    const { [key]: _, ...rest } = draft.tags;
    updateDraft({ tags: rest });
  };

  return (
    <SpaceBetween size="l">
      <Container header={<Header variant="h2">리소스 태그</Header>}>
        <SpaceBetween size="m">
          <Table
            items={tags.map(([k, v]) => ({ key: k, value: v }))}
            columnDefinitions={[
              { id: "key", header: "Key", cell: (item) => item.key },
              { id: "value", header: "Value", cell: (item) => item.value },
              { id: "actions", header: "", cell: (item) => <Button variant="icon" iconName="remove" onClick={() => removeTag(item.key)} data-testid={`remove-tag-${item.key}`} /> },
            ]}
            empty="태그가 없습니다."
            data-testid="tags-table"
          />
          <SpaceBetween size="s" direction="horizontal">
            <FormField label="Key" constraintText="aws: 접두사 불가, ≤128자">
              <Input value={newKey} onChange={({ detail }) => setNewKey(detail.value)} placeholder="Project" data-testid="tag-key-input" />
            </FormField>
            <FormField label="Value" constraintText="≤256자">
              <Input value={newValue} onChange={({ detail }) => setNewValue(detail.value)} placeholder="claude-code" data-testid="tag-value-input" />
            </FormField>
            <Button onClick={addTag} data-testid="add-tag-button">추가</Button>
          </SpaceBetween>
        </SpaceBetween>
      </Container>
    </SpaceBetween>
  );
}
