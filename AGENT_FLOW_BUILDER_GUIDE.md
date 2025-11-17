# Agent Flow Builder - User Guide

Quick guide for using the Visual Agent Flow Builder.

## Getting Started

### Opening the Flow Builder

```typescript
import { FlowBuilder } from '@/components/agents/FlowBuilder';

<FlowBuilder
  agentId="your-agent-id"
  onSave={handleSave}
/>
```

---

## Building Your First Flow

### Step 1: Add a Start Node

1. Find "Start" in the left toolbar
2. Drag it onto the canvas
3. Click the node to configure the initial greeting

### Step 2: Add More Nodes

1. Drag desired node types from toolbar
2. Position them on canvas
3. Connect nodes by dragging from output handles to input handles

### Step 3: Configure Nodes

1. Click any node to open configuration panel
2. Fill in required fields
3. Changes auto-save after 2 seconds

### Step 4: Validate

1. Check validation errors at top of screen
2. Fix any issues highlighted in red
3. Ensure flow starts with Start node and ends with End node

---

## Node Types Reference

### Start Node (Green)
**Purpose:** Entry point of conversation
**Configuration:**
- Label: Display name
- Greeting: Initial message to user

**Example:**
```
Label: "Conversation Start"
Greeting: "Hello! How can I assist you today?"
```

### Message Node (Blue)
**Purpose:** Agent speaks a message
**Configuration:**
- Label: Display name
- Message: Text to speak
- Variables: Dynamic values to insert

**Example:**
```
Label: "Welcome Message"
Message: "Hello {{user_name}}, welcome to our service!"
Variables: ["user_name"]
```

### Question Node (Purple)
**Purpose:** Ask user a question and save response
**Configuration:**
- Label: Display name
- Question: Text to ask
- Response Type: text, number, yes/no, choice
- Variable Name: Where to save answer
- Choices: Options for multiple choice

**Example:**
```
Label: "Get Name"
Question: "What is your name?"
Response Type: text
Variable Name: "user_name"
```

### Decision Node (Amber)
**Purpose:** Branch based on condition
**Configuration:**
- Label: Display name
- Variable: Variable to check
- Operator: equals, not_equals, contains, etc.
- Value: Comparison value
- Condition: Full expression

**Example:**
```
Label: "Check Intent"
Variable: "user_intent"
Operator: equals
Value: "support"
Condition: "{{user_intent}} == support"
```

**Outputs:**
- Green handle: True branch
- Red handle: False branch

### Function Node (Indigo)
**Purpose:** Call external API or function
**Configuration:**
- Label: Display name
- Function Name: Name of function
- Function Type: api_call, integration, custom
- Method: GET, POST, PUT, DELETE
- Endpoint: API URL
- Response Variable: Where to save result
- Retry on Failure: Yes/No

**Example:**
```
Label: "Get Customer Data"
Function Type: api_call
Method: GET
Endpoint: "https://api.example.com/customers/{{customer_id}}"
Response Variable: "customer_data"
Retry on Failure: Yes
```

**Outputs:**
- Green handle: Success
- Red handle: Error

### Transfer Node (Cyan)
**Purpose:** Transfer call to human or another agent
**Configuration:**
- Label: Display name
- Transfer Type: human, agent, phone_number
- Department: For human transfer
- Target Agent: For agent transfer
- Phone Number: For phone transfer
- Message: What to say before transfer
- Wait Music: Yes/No

**Example:**
```
Label: "Transfer to Support"
Transfer Type: human
Department: "Customer Support"
Message: "Let me transfer you to our support team"
Wait Music: Yes
```

### End Node (Gray/Colored)
**Purpose:** End the conversation
**Configuration:**
- Label: Display name
- Farewell: Final message
- Reason: completed, user_hangup, timeout, error, transferred
- Collect Feedback: Yes/No

**Example:**
```
Label: "End Call"
Farewell: "Thank you for calling. Have a great day!"
Reason: completed
Collect Feedback: Yes
```

**Colors by Reason:**
- Green: completed
- Blue: transferred
- Red: error
- Orange: timeout
- Gray: user_hangup

---

## Variables

### Using Variables

**In Message/Question Text:**
```
"Hello {{user_name}}, your order {{order_id}} is ready!"
```

**Saving Variables:**
- Question nodes automatically save to specified variable
- Function nodes save response to specified variable

**Variable Naming:**
- Use lowercase
- Use underscores for spaces
- Be descriptive

**Examples:**
- `user_name`
- `order_id`
- `customer_email`
- `support_ticket_number`

---

## Connecting Nodes

### Creating Connections

1. **Click and Drag:**
   - Click on output handle (right side)
   - Drag to input handle (left side)
   - Release to create connection

2. **Valid Connections:**
   - Start → Any node except Start
   - Any node → End
   - Cannot connect End → anywhere
   - Cannot connect anywhere → Start

3. **Special Connections:**
   - Decision nodes have 2 outputs (true/false)
   - Function nodes have 2 outputs (success/error)
   - Connect both branches for complete flow

---

## Validation Errors

### Common Errors

**"Flow must have exactly one Start node"**
- Add a Start node if missing
- Remove extra Start nodes if multiple

**"Node has no outgoing connections"**
- Connect the node to next step
- All nodes except End must have outputs

**"Message node has no message text"**
- Click node and add message in config panel

**"Decision node should have exactly 2 outgoing connections"**
- Connect both true and false branches

**"Node is unreachable from Start node"**
- Ensure path exists from Start to this node
- Check for disconnected branches

---

## Keyboard Shortcuts

| Action | Shortcut |
|--------|----------|
| Delete selected node | `Del` |
| Zoom in | `+` |
| Zoom out | `-` |
| Fit view | `F` |
| Deselect | `Esc` |
| Pan canvas | Hold `Space` + drag |

---

## Tips & Best Practices

### Flow Design

1. **Start Simple:**
   - Begin with Start → Message → End
   - Add complexity gradually

2. **Use Descriptive Labels:**
   - Name nodes clearly
   - Future you will thank you

3. **Group Related Nodes:**
   - Keep related logic together
   - Use visual spacing

4. **Plan Branches:**
   - Map out decision points
   - Handle all outcomes

### Variables

1. **Consistent Naming:**
   - Use same format throughout
   - Document complex variables

2. **Save Important Data:**
   - User responses
   - API results
   - Decision outcomes

3. **Use in Messages:**
   - Personalize with {{user_name}}
   - Reference previous answers

### Error Handling

1. **Add Error Branches:**
   - Handle function failures
   - Provide fallback paths

2. **Timeout Paths:**
   - Add End nodes for timeouts
   - Graceful degradation

3. **Transfer Option:**
   - Always offer human fallback
   - For complex issues

### Testing

1. **Validate Early:**
   - Fix errors as you build
   - Don't wait until end

2. **Test All Paths:**
   - True and false branches
   - Success and error paths

3. **Use Test Flow:**
   - Click "Test Flow" button
   - Verify logic works

---

## Example Flows

### Simple Support Flow

```
Start (Greeting)
  ↓
Question (Ask reason for call)
  ↓
Decision (Check if technical or billing)
  ├─ True: Transfer (Technical Support)
  └─ False: Transfer (Billing Department)
```

### Order Status Flow

```
Start (Greeting)
  ↓
Question (Ask for order number)
  ↓
Function (API: Get order status)
  ├─ Success: Message (Share status)
  │    ↓
  │   End (Goodbye)
  └─ Error: Message (Order not found)
       ↓
      Transfer (Customer Service)
```

### Qualification Flow

```
Start (Greeting)
  ↓
Question (Company size?)
  ↓
Decision (Size > 50?)
  ├─ True: Question (Annual revenue?)
  │    ↓
  │   Decision (Revenue > $1M?)
  │    ├─ True: Transfer (Sales)
  │    └─ False: Message (Info) → End
  └─ False: Message (Self-service) → End
```

---

## Troubleshooting

### Nodes Won't Connect

**Problem:** Can't create connection between nodes
**Solutions:**
- Check if source has output handle
- Check if target has input handle
- Verify not connecting to Start
- Verify not connecting from End

### Auto-Save Not Working

**Problem:** Changes aren't saving
**Solutions:**
- Wait 2 seconds after last change
- Check browser console for errors
- Verify onSave prop is provided
- Check network connectivity

### Validation Won't Clear

**Problem:** Errors persist after fixing
**Solutions:**
- Make sure you saved changes (click outside)
- Refresh the validation panel
- Check if all errors are actually fixed
- Verify node connections exist

### Drag-and-Drop Not Working

**Problem:** Can't drag nodes from toolbar
**Solutions:**
- Check browser compatibility
- Disable browser extensions
- Try different browser
- Check if canvas is responsive

---

## Advanced Features

### Export Flow

1. Click "Export" button
2. Choose save location
3. JSON file downloads with full flow data

### Import Flow

```typescript
const savedFlow = JSON.parse(flowData);
<FlowBuilder initialFlow={savedFlow} />
```

### Read-Only Mode

```typescript
<FlowBuilder
  initialFlow={flow}
  readOnly={true}
/>
```

### Custom Styling

All nodes use Tailwind CSS classes and can be customized via theme.

---

## Support

### Documentation
- [Complete Summary](./AGENT_FLOW_BUILDER_SUMMARY.md)
- [API Reference](./AGENT_FLOW_BUILDER_SUMMARY.md#node-data-structures)

### Common Issues
- Check validation panel for errors
- Ensure all required fields are filled
- Verify flow structure (Start → ... → End)
- Test all branches

### Best Practices
- Auto-save happens every 2 seconds
- Use validation to catch errors early
- Test flows before deploying
- Keep flows simple and focused

---

## Quick Start Checklist

- [ ] Add Start node
- [ ] Configure initial greeting
- [ ] Add conversation nodes (Message, Question, etc.)
- [ ] Connect all nodes
- [ ] Add at least one End node
- [ ] Check validation errors
- [ ] Fix any issues
- [ ] Test the flow
- [ ] Save/Export

Happy building! 🚀
