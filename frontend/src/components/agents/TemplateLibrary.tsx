import React, { useState } from 'react';
import { Node, Edge } from 'react-flow-renderer';
import {
  BookTemplate,
  Phone,
  Calendar,
  ShoppingCart,
  HelpCircle,
  FileText,
  TrendingUp,
  Copy,
  Eye,
  X,
} from 'lucide-react';

interface FlowTemplate {
  id: string;
  name: string;
  description: string;
  category: 'support' | 'sales' | 'booking' | 'ecommerce' | 'general';
  icon: React.ReactNode;
  nodes: Node[];
  edges: Edge[];
  preview?: string;
}

interface TemplateLibraryProps {
  onApplyTemplate: (nodes: Node[], edges: Edge[]) => void;
  onClose: () => void;
}

const templates: FlowTemplate[] = [
  {
    id: 'customer-support',
    name: 'Customer Support Flow',
    description: 'Basic customer support routing with department transfer',
    category: 'support',
    icon: <HelpCircle className="w-5 h-5" />,
    nodes: [
      {
        id: 'start-1',
        type: 'start',
        position: { x: 100, y: 200 },
        data: {
          label: 'Start',
          greeting: 'Hello! Thank you for calling our support line. How can I help you today?',
        },
      },
      {
        id: 'question-1',
        type: 'question',
        position: { x: 400, y: 200 },
        data: {
          label: 'Ask Issue Type',
          question: 'Are you calling about a technical issue or a billing question?',
          expectedResponseType: 'choice',
          choices: ['Technical Issue', 'Billing Question', 'Other'],
          variableName: 'issue_type',
        },
      },
      {
        id: 'decision-1',
        type: 'decision',
        position: { x: 700, y: 150 },
        data: {
          label: 'Check Issue Type',
          variable: 'issue_type',
          operator: 'equals',
          value: 'Technical Issue',
          condition: '{{issue_type}} == "Technical Issue"',
        },
      },
      {
        id: 'transfer-1',
        type: 'transfer',
        position: { x: 1000, y: 100 },
        data: {
          label: 'Transfer to Tech Support',
          transferType: 'human',
          department: 'Technical Support',
          message: 'Let me transfer you to our technical support team.',
          waitMusic: true,
        },
      },
      {
        id: 'transfer-2',
        type: 'transfer',
        position: { x: 1000, y: 250 },
        data: {
          label: 'Transfer to Billing',
          transferType: 'human',
          department: 'Billing',
          message: 'Let me connect you with our billing department.',
          waitMusic: true,
        },
      },
      {
        id: 'end-1',
        type: 'end',
        position: { x: 1300, y: 175 },
        data: {
          label: 'End Call',
          farewell: 'Thank you for calling. Have a great day!',
          reason: 'transferred',
          collectFeedback: false,
        },
      },
    ],
    edges: [
      { id: 'e1', source: 'start-1', target: 'question-1', type: 'smoothstep', animated: true },
      { id: 'e2', source: 'question-1', target: 'decision-1', type: 'smoothstep', animated: true },
      { id: 'e3', source: 'decision-1', target: 'transfer-1', sourceHandle: 'true', type: 'smoothstep', animated: true },
      { id: 'e4', source: 'decision-1', target: 'transfer-2', sourceHandle: 'false', type: 'smoothstep', animated: true },
      { id: 'e5', source: 'transfer-1', target: 'end-1', type: 'smoothstep', animated: true },
      { id: 'e6', source: 'transfer-2', target: 'end-1', type: 'smoothstep', animated: true },
    ],
  },
  {
    id: 'lead-qualification',
    name: 'Lead Qualification Flow',
    description: 'Qualify sales leads based on company size and budget',
    category: 'sales',
    icon: <TrendingUp className="w-5 h-5" />,
    nodes: [
      {
        id: 'start-1',
        type: 'start',
        position: { x: 100, y: 250 },
        data: {
          label: 'Start',
          greeting: 'Hi! Thanks for your interest in our product. I have a few questions to help us serve you better.',
        },
      },
      {
        id: 'question-1',
        type: 'question',
        position: { x: 400, y: 200 },
        data: {
          label: 'Company Size',
          question: 'How many employees does your company have?',
          expectedResponseType: 'choice',
          choices: ['1-10', '11-50', '51-200', '200+'],
          variableName: 'company_size',
        },
      },
      {
        id: 'question-2',
        type: 'question',
        position: { x: 400, y: 350 },
        data: {
          label: 'Annual Budget',
          question: 'What is your estimated annual budget for this solution?',
          expectedResponseType: 'choice',
          choices: ['Under $10k', '$10k-$50k', '$50k-$100k', '$100k+'],
          variableName: 'budget',
        },
      },
      {
        id: 'decision-1',
        type: 'decision',
        position: { x: 700, y: 275 },
        data: {
          label: 'Qualified?',
          variable: 'budget',
          operator: 'equals',
          value: '$50k-$100k',
          condition: '{{budget}} in ["$50k-$100k", "$100k+"]',
        },
      },
      {
        id: 'function-1',
        type: 'function',
        position: { x: 1000, y: 200 },
        data: {
          label: 'Create Lead in CRM',
          functionName: 'createLead',
          functionType: 'api_call',
          method: 'POST',
          endpoint: 'https://api.crm.example.com/leads',
          parameters: {
            company_size: '{{company_size}}',
            budget: '{{budget}}',
            qualified: true,
          },
          responseVariable: 'lead_id',
          retryOnFailure: true,
        },
      },
      {
        id: 'transfer-1',
        type: 'transfer',
        position: { x: 1300, y: 200 },
        data: {
          label: 'Transfer to Sales',
          transferType: 'human',
          department: 'Sales',
          message: 'Great! Let me connect you with one of our sales representatives.',
          waitMusic: true,
        },
      },
      {
        id: 'message-1',
        type: 'message',
        position: { x: 1000, y: 350 },
        data: {
          label: 'Self-Service Info',
          message: 'Thank you for your interest! We\'ll send you information about our self-service plans via email.',
          variableInputs: [],
        },
      },
      {
        id: 'end-1',
        type: 'end',
        position: { x: 1600, y: 275 },
        data: {
          label: 'End Call',
          farewell: 'Thanks for your time. We\'ll be in touch soon!',
          reason: 'completed',
          collectFeedback: true,
        },
      },
    ],
    edges: [
      { id: 'e1', source: 'start-1', target: 'question-1', type: 'smoothstep', animated: true },
      { id: 'e2', source: 'question-1', target: 'question-2', type: 'smoothstep', animated: true },
      { id: 'e3', source: 'question-2', target: 'decision-1', type: 'smoothstep', animated: true },
      { id: 'e4', source: 'decision-1', target: 'function-1', sourceHandle: 'true', type: 'smoothstep', animated: true },
      { id: 'e5', source: 'decision-1', target: 'message-1', sourceHandle: 'false', type: 'smoothstep', animated: true },
      { id: 'e6', source: 'function-1', target: 'transfer-1', sourceHandle: 'success', type: 'smoothstep', animated: true },
      { id: 'e7', source: 'transfer-1', target: 'end-1', type: 'smoothstep', animated: true },
      { id: 'e8', source: 'message-1', target: 'end-1', type: 'smoothstep', animated: true },
    ],
  },
  {
    id: 'appointment-booking',
    name: 'Appointment Booking Flow',
    description: 'Book appointments with calendar integration',
    category: 'booking',
    icon: <Calendar className="w-5 h-5" />,
    nodes: [
      {
        id: 'start-1',
        type: 'start',
        position: { x: 100, y: 200 },
        data: {
          label: 'Start',
          greeting: 'Hello! I can help you schedule an appointment. Let me get some information from you.',
        },
      },
      {
        id: 'question-1',
        type: 'question',
        position: { x: 400, y: 150 },
        data: {
          label: 'Get Name',
          question: 'What is your full name?',
          expectedResponseType: 'text',
          variableName: 'customer_name',
        },
      },
      {
        id: 'question-2',
        type: 'question',
        position: { x: 400, y: 280 },
        data: {
          label: 'Get Phone',
          question: 'What is your phone number?',
          expectedResponseType: 'text',
          variableName: 'phone_number',
        },
      },
      {
        id: 'function-1',
        type: 'function',
        position: { x: 700, y: 200 },
        data: {
          label: 'Check Availability',
          functionName: 'checkAvailability',
          functionType: 'api_call',
          method: 'GET',
          endpoint: 'https://api.calendar.example.com/availability',
          responseVariable: 'available_slots',
          retryOnFailure: true,
        },
      },
      {
        id: 'question-3',
        type: 'question',
        position: { x: 1000, y: 200 },
        data: {
          label: 'Select Time',
          question: 'Which time slot works best for you?',
          expectedResponseType: 'choice',
          choices: ['{{available_slots}}'],
          variableName: 'selected_time',
        },
      },
      {
        id: 'function-2',
        type: 'function',
        position: { x: 1300, y: 200 },
        data: {
          label: 'Book Appointment',
          functionName: 'bookAppointment',
          functionType: 'api_call',
          method: 'POST',
          endpoint: 'https://api.calendar.example.com/appointments',
          parameters: {
            name: '{{customer_name}}',
            phone: '{{phone_number}}',
            time: '{{selected_time}}',
          },
          responseVariable: 'confirmation_id',
          retryOnFailure: true,
        },
      },
      {
        id: 'message-1',
        type: 'message',
        position: { x: 1600, y: 150 },
        data: {
          label: 'Confirmation',
          message: 'Perfect! Your appointment is confirmed for {{selected_time}}. Confirmation number: {{confirmation_id}}',
          variableInputs: ['selected_time', 'confirmation_id'],
        },
      },
      {
        id: 'message-2',
        type: 'message',
        position: { x: 1600, y: 300 },
        data: {
          label: 'Error Message',
          message: 'I apologize, but there was an issue booking your appointment. Let me transfer you to our booking team.',
          variableInputs: [],
        },
      },
      {
        id: 'transfer-1',
        type: 'transfer',
        position: { x: 1900, y: 300 },
        data: {
          label: 'Transfer to Booking',
          transferType: 'human',
          department: 'Booking',
          message: 'Transferring you now.',
          waitMusic: true,
        },
      },
      {
        id: 'end-1',
        type: 'end',
        position: { x: 1900, y: 200 },
        data: {
          label: 'End Call',
          farewell: 'Thank you! We look forward to seeing you.',
          reason: 'completed',
          collectFeedback: true,
        },
      },
    ],
    edges: [
      { id: 'e1', source: 'start-1', target: 'question-1', type: 'smoothstep', animated: true },
      { id: 'e2', source: 'question-1', target: 'question-2', type: 'smoothstep', animated: true },
      { id: 'e3', source: 'question-2', target: 'function-1', type: 'smoothstep', animated: true },
      { id: 'e4', source: 'function-1', target: 'question-3', sourceHandle: 'success', type: 'smoothstep', animated: true },
      { id: 'e5', source: 'question-3', target: 'function-2', type: 'smoothstep', animated: true },
      { id: 'e6', source: 'function-2', target: 'message-1', sourceHandle: 'success', type: 'smoothstep', animated: true },
      { id: 'e7', source: 'function-2', target: 'message-2', sourceHandle: 'error', type: 'smoothstep', animated: true },
      { id: 'e8', source: 'message-1', target: 'end-1', type: 'smoothstep', animated: true },
      { id: 'e9', source: 'message-2', target: 'transfer-1', type: 'smoothstep', animated: true },
      { id: 'e10', source: 'transfer-1', target: 'end-1', type: 'smoothstep', animated: true },
    ],
  },
  {
    id: 'order-status',
    name: 'Order Status Check',
    description: 'Check order status with API integration',
    category: 'ecommerce',
    icon: <ShoppingCart className="w-5 h-5" />,
    nodes: [
      {
        id: 'start-1',
        type: 'start',
        position: { x: 100, y: 200 },
        data: {
          label: 'Start',
          greeting: 'Hello! I can help you check your order status. Let me get your order number.',
        },
      },
      {
        id: 'question-1',
        type: 'question',
        position: { x: 400, y: 200 },
        data: {
          label: 'Get Order Number',
          question: 'What is your order number?',
          expectedResponseType: 'text',
          variableName: 'order_number',
        },
      },
      {
        id: 'function-1',
        type: 'function',
        position: { x: 700, y: 200 },
        data: {
          label: 'Fetch Order Status',
          functionName: 'getOrderStatus',
          functionType: 'api_call',
          method: 'GET',
          endpoint: 'https://api.store.example.com/orders/{{order_number}}',
          responseVariable: 'order_data',
          retryOnFailure: true,
        },
      },
      {
        id: 'message-1',
        type: 'message',
        position: { x: 1000, y: 150 },
        data: {
          label: 'Share Status',
          message: 'Your order {{order_number}} is currently {{order_data.status}}. Expected delivery: {{order_data.delivery_date}}',
          variableInputs: ['order_number', 'order_data'],
        },
      },
      {
        id: 'message-2',
        type: 'message',
        position: { x: 1000, y: 300 },
        data: {
          label: 'Order Not Found',
          message: 'I could not find an order with that number. Please verify the order number and try again, or let me transfer you to customer service.',
          variableInputs: [],
        },
      },
      {
        id: 'question-2',
        type: 'question',
        position: { x: 1300, y: 300 },
        data: {
          label: 'Need Help?',
          question: 'Would you like to speak with customer service?',
          expectedResponseType: 'yes_no',
          variableName: 'needs_help',
        },
      },
      {
        id: 'decision-1',
        type: 'decision',
        position: { x: 1600, y: 300 },
        data: {
          label: 'Check Response',
          variable: 'needs_help',
          operator: 'equals',
          value: 'yes',
          condition: '{{needs_help}} == "yes"',
        },
      },
      {
        id: 'transfer-1',
        type: 'transfer',
        position: { x: 1900, y: 250 },
        data: {
          label: 'Transfer to Support',
          transferType: 'human',
          department: 'Customer Service',
          message: 'Let me connect you with customer service.',
          waitMusic: true,
        },
      },
      {
        id: 'end-1',
        type: 'end',
        position: { x: 1300, y: 150 },
        data: {
          label: 'End - Success',
          farewell: 'Is there anything else I can help you with? If not, have a great day!',
          reason: 'completed',
          collectFeedback: true,
        },
      },
      {
        id: 'end-2',
        type: 'end',
        position: { x: 1900, y: 350 },
        data: {
          label: 'End - No Help',
          farewell: 'Okay, feel free to call back if you need assistance. Goodbye!',
          reason: 'completed',
          collectFeedback: false,
        },
      },
    ],
    edges: [
      { id: 'e1', source: 'start-1', target: 'question-1', type: 'smoothstep', animated: true },
      { id: 'e2', source: 'question-1', target: 'function-1', type: 'smoothstep', animated: true },
      { id: 'e3', source: 'function-1', target: 'message-1', sourceHandle: 'success', type: 'smoothstep', animated: true },
      { id: 'e4', source: 'function-1', target: 'message-2', sourceHandle: 'error', type: 'smoothstep', animated: true },
      { id: 'e5', source: 'message-1', target: 'end-1', type: 'smoothstep', animated: true },
      { id: 'e6', source: 'message-2', target: 'question-2', type: 'smoothstep', animated: true },
      { id: 'e7', source: 'question-2', target: 'decision-1', type: 'smoothstep', animated: true },
      { id: 'e8', source: 'decision-1', target: 'transfer-1', sourceHandle: 'true', type: 'smoothstep', animated: true },
      { id: 'e9', source: 'decision-1', target: 'end-2', sourceHandle: 'false', type: 'smoothstep', animated: true },
      { id: 'e10', source: 'transfer-1', target: 'end-1', type: 'smoothstep', animated: true },
    ],
  },
  {
    id: 'simple-greeting',
    name: 'Simple Greeting Flow',
    description: 'Basic conversation flow for getting started',
    category: 'general',
    icon: <Phone className="w-5 h-5" />,
    nodes: [
      {
        id: 'start-1',
        type: 'start',
        position: { x: 100, y: 200 },
        data: {
          label: 'Start',
          greeting: 'Hello! Welcome to our service.',
        },
      },
      {
        id: 'message-1',
        type: 'message',
        position: { x: 400, y: 200 },
        data: {
          label: 'Welcome Message',
          message: 'Thank you for calling. How can I assist you today?',
          variableInputs: [],
        },
      },
      {
        id: 'end-1',
        type: 'end',
        position: { x: 700, y: 200 },
        data: {
          label: 'End Call',
          farewell: 'Thank you for calling. Have a great day!',
          reason: 'completed',
          collectFeedback: false,
        },
      },
    ],
    edges: [
      { id: 'e1', source: 'start-1', target: 'message-1', type: 'smoothstep', animated: true },
      { id: 'e2', source: 'message-1', target: 'end-1', type: 'smoothstep', animated: true },
    ],
  },
  {
    id: 'survey-flow',
    name: 'Customer Survey Flow',
    description: 'Collect customer feedback with multiple questions',
    category: 'general',
    icon: <FileText className="w-5 h-5" />,
    nodes: [
      {
        id: 'start-1',
        type: 'start',
        position: { x: 100, y: 250 },
        data: {
          label: 'Start',
          greeting: 'Hi! We would love to get your feedback. This will only take a minute.',
        },
      },
      {
        id: 'question-1',
        type: 'question',
        position: { x: 400, y: 150 },
        data: {
          label: 'Satisfaction Rating',
          question: 'On a scale of 1 to 5, how satisfied are you with our service?',
          expectedResponseType: 'choice',
          choices: ['1', '2', '3', '4', '5'],
          variableName: 'satisfaction_rating',
        },
      },
      {
        id: 'question-2',
        type: 'question',
        position: { x: 400, y: 280 },
        data: {
          label: 'Likelihood to Recommend',
          question: 'How likely are you to recommend us to a friend? (1-10)',
          expectedResponseType: 'choice',
          choices: ['1', '2', '3', '4', '5', '6', '7', '8', '9', '10'],
          variableName: 'nps_score',
        },
      },
      {
        id: 'question-3',
        type: 'question',
        position: { x: 400, y: 410 },
        data: {
          label: 'Open Feedback',
          question: 'Is there anything specific you would like us to improve?',
          expectedResponseType: 'text',
          variableName: 'feedback_comments',
        },
      },
      {
        id: 'function-1',
        type: 'function',
        position: { x: 700, y: 280 },
        data: {
          label: 'Save Survey Results',
          functionName: 'saveSurvey',
          functionType: 'api_call',
          method: 'POST',
          endpoint: 'https://api.feedback.example.com/surveys',
          parameters: {
            satisfaction: '{{satisfaction_rating}}',
            nps: '{{nps_score}}',
            comments: '{{feedback_comments}}',
          },
          responseVariable: 'survey_id',
          retryOnFailure: true,
        },
      },
      {
        id: 'message-1',
        type: 'message',
        position: { x: 1000, y: 280 },
        data: {
          label: 'Thank You',
          message: 'Thank you so much for your valuable feedback! We truly appreciate it.',
          variableInputs: [],
        },
      },
      {
        id: 'end-1',
        type: 'end',
        position: { x: 1300, y: 280 },
        data: {
          label: 'End Call',
          farewell: 'Have a wonderful day!',
          reason: 'completed',
          collectFeedback: false,
        },
      },
    ],
    edges: [
      { id: 'e1', source: 'start-1', target: 'question-1', type: 'smoothstep', animated: true },
      { id: 'e2', source: 'question-1', target: 'question-2', type: 'smoothstep', animated: true },
      { id: 'e3', source: 'question-2', target: 'question-3', type: 'smoothstep', animated: true },
      { id: 'e4', source: 'question-3', target: 'function-1', type: 'smoothstep', animated: true },
      { id: 'e5', source: 'function-1', target: 'message-1', sourceHandle: 'success', type: 'smoothstep', animated: true },
      { id: 'e6', source: 'message-1', target: 'end-1', type: 'smoothstep', animated: true },
    ],
  },
];

export const TemplateLibrary: React.FC<TemplateLibraryProps> = ({ onApplyTemplate, onClose }) => {
  const [selectedCategory, setSelectedCategory] = useState<string>('all');
  const [selectedTemplate, setSelectedTemplate] = useState<FlowTemplate | null>(null);
  const [previewMode, setPreviewMode] = useState(false);

  const categories = [
    { id: 'all', name: 'All Templates', icon: <BookTemplate className="w-4 h-4" /> },
    { id: 'support', name: 'Customer Support', icon: <HelpCircle className="w-4 h-4" /> },
    { id: 'sales', name: 'Sales & Leads', icon: <TrendingUp className="w-4 h-4" /> },
    { id: 'booking', name: 'Appointments', icon: <Calendar className="w-4 h-4" /> },
    { id: 'ecommerce', name: 'E-Commerce', icon: <ShoppingCart className="w-4 h-4" /> },
    { id: 'general', name: 'General', icon: <FileText className="w-4 h-4" /> },
  ];

  const filteredTemplates =
    selectedCategory === 'all'
      ? templates
      : templates.filter((t) => t.category === selectedCategory);

  const handleApplyTemplate = (template: FlowTemplate) => {
    // Generate unique IDs for nodes and edges
    const nodeIdMap = new Map<string, string>();
    const newNodes = template.nodes.map((node) => {
      const newId = `node-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
      nodeIdMap.set(node.id, newId);
      return {
        ...node,
        id: newId,
      };
    });

    const newEdges = template.edges.map((edge, idx) => ({
      ...edge,
      id: `edge-${Date.now()}-${idx}`,
      source: nodeIdMap.get(edge.source) || edge.source,
      target: nodeIdMap.get(edge.target) || edge.target,
    }));

    onApplyTemplate(newNodes, newEdges);
    onClose();
  };

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
      <div className="bg-white rounded-lg shadow-2xl w-[90vw] h-[85vh] max-w-6xl flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b">
          <div className="flex items-center gap-3">
            <BookTemplate className="w-6 h-6 text-indigo-600" />
            <h2 className="text-2xl font-bold text-gray-900">Flow Templates</h2>
          </div>
          <button
            onClick={onClose}
            className="p-2 hover:bg-gray-100 rounded-lg transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        <div className="flex-1 flex overflow-hidden">
          {/* Sidebar - Categories */}
          <div className="w-64 border-r bg-gray-50 p-4 overflow-y-auto">
            <h3 className="text-sm font-semibold text-gray-600 uppercase mb-3">Categories</h3>
            <div className="space-y-1">
              {categories.map((category) => (
                <button
                  key={category.id}
                  onClick={() => setSelectedCategory(category.id)}
                  className={`w-full flex items-center gap-3 px-3 py-2 rounded-lg transition-colors ${
                    selectedCategory === category.id
                      ? 'bg-indigo-100 text-indigo-700 font-medium'
                      : 'text-gray-700 hover:bg-gray-100'
                  }`}
                >
                  {category.icon}
                  <span>{category.name}</span>
                </button>
              ))}
            </div>
          </div>

          {/* Main Content */}
          <div className="flex-1 flex flex-col overflow-hidden">
            {!previewMode ? (
              <>
                {/* Template Grid */}
                <div className="flex-1 p-6 overflow-y-auto">
                  <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                    {filteredTemplates.map((template) => (
                      <div
                        key={template.id}
                        className={`bg-white border-2 rounded-lg p-5 cursor-pointer transition-all hover:shadow-lg ${
                          selectedTemplate?.id === template.id
                            ? 'border-indigo-500 shadow-md'
                            : 'border-gray-200'
                        }`}
                        onClick={() => setSelectedTemplate(template)}
                      >
                        {/* Template Icon & Name */}
                        <div className="flex items-start gap-3 mb-3">
                          <div className="p-3 bg-indigo-100 rounded-lg text-indigo-600">
                            {template.icon}
                          </div>
                          <div className="flex-1">
                            <h3 className="font-semibold text-gray-900 mb-1">{template.name}</h3>
                            <p className="text-sm text-gray-500">{template.description}</p>
                          </div>
                        </div>

                        {/* Template Stats */}
                        <div className="flex items-center gap-4 text-xs text-gray-500 mb-4">
                          <span>{template.nodes.length} nodes</span>
                          <span>{template.edges.length} connections</span>
                        </div>

                        {/* Actions */}
                        {selectedTemplate?.id === template.id && (
                          <div className="flex gap-2">
                            <button
                              onClick={(e) => {
                                e.stopPropagation();
                                setPreviewMode(true);
                              }}
                              className="flex-1 flex items-center justify-center gap-2 px-3 py-2 bg-gray-100 hover:bg-gray-200 rounded-lg text-sm font-medium transition-colors"
                            >
                              <Eye className="w-4 h-4" />
                              Preview
                            </button>
                            <button
                              onClick={(e) => {
                                e.stopPropagation();
                                handleApplyTemplate(template);
                              }}
                              className="flex-1 flex items-center justify-center gap-2 px-3 py-2 bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg text-sm font-medium transition-colors"
                            >
                              <Copy className="w-4 h-4" />
                              Use Template
                            </button>
                          </div>
                        )}
                      </div>
                    ))}
                  </div>

                  {filteredTemplates.length === 0 && (
                    <div className="flex flex-col items-center justify-center h-64 text-gray-400">
                      <BookTemplate className="w-16 h-16 mb-3" />
                      <p>No templates found in this category</p>
                    </div>
                  )}
                </div>
              </>
            ) : (
              <>
                {/* Preview Mode */}
                <div className="flex-1 p-6 overflow-y-auto">
                  <button
                    onClick={() => setPreviewMode(false)}
                    className="mb-4 px-4 py-2 text-sm text-gray-600 hover:bg-gray-100 rounded-lg transition-colors"
                  >
                    ← Back to Templates
                  </button>

                  {selectedTemplate && (
                    <div>
                      <div className="flex items-start justify-between mb-6">
                        <div>
                          <h3 className="text-2xl font-bold text-gray-900 mb-2">
                            {selectedTemplate.name}
                          </h3>
                          <p className="text-gray-600">{selectedTemplate.description}</p>
                        </div>
                        <button
                          onClick={() => handleApplyTemplate(selectedTemplate)}
                          className="flex items-center gap-2 px-4 py-2 bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg font-medium transition-colors"
                        >
                          <Copy className="w-4 h-4" />
                          Use This Template
                        </button>
                      </div>

                      {/* Flow Breakdown */}
                      <div className="space-y-6">
                        <div>
                          <h4 className="font-semibold text-gray-900 mb-3">Flow Overview</h4>
                          <div className="bg-gray-50 rounded-lg p-4">
                            <div className="grid grid-cols-2 gap-4 text-sm">
                              <div>
                                <span className="text-gray-600">Total Nodes:</span>
                                <span className="ml-2 font-medium">{selectedTemplate.nodes.length}</span>
                              </div>
                              <div>
                                <span className="text-gray-600">Connections:</span>
                                <span className="ml-2 font-medium">{selectedTemplate.edges.length}</span>
                              </div>
                              <div>
                                <span className="text-gray-600">Category:</span>
                                <span className="ml-2 font-medium capitalize">
                                  {selectedTemplate.category}
                                </span>
                              </div>
                            </div>
                          </div>
                        </div>

                        {/* Node Breakdown */}
                        <div>
                          <h4 className="font-semibold text-gray-900 mb-3">Nodes in This Flow</h4>
                          <div className="space-y-3">
                            {selectedTemplate.nodes.map((node, idx) => (
                              <div key={node.id} className="bg-white border rounded-lg p-4">
                                <div className="flex items-start gap-3">
                                  <div className="flex items-center justify-center w-8 h-8 bg-indigo-100 text-indigo-600 rounded-full text-sm font-medium">
                                    {idx + 1}
                                  </div>
                                  <div className="flex-1">
                                    <div className="flex items-center gap-2 mb-1">
                                      <span className="font-medium text-gray-900">
                                        {node.data.label || node.id}
                                      </span>
                                      <span className="px-2 py-0.5 bg-gray-100 text-gray-600 text-xs rounded-full capitalize">
                                        {node.type}
                                      </span>
                                    </div>
                                    {node.type === 'start' && (
                                      <p className="text-sm text-gray-600">{node.data.greeting}</p>
                                    )}
                                    {node.type === 'message' && (
                                      <p className="text-sm text-gray-600">{node.data.message}</p>
                                    )}
                                    {node.type === 'question' && (
                                      <p className="text-sm text-gray-600">{node.data.question}</p>
                                    )}
                                    {node.type === 'decision' && (
                                      <p className="text-sm text-gray-600">
                                        Condition: {node.data.condition}
                                      </p>
                                    )}
                                    {node.type === 'function' && (
                                      <p className="text-sm text-gray-600">
                                        {node.data.method} {node.data.endpoint}
                                      </p>
                                    )}
                                    {node.type === 'transfer' && (
                                      <p className="text-sm text-gray-600">
                                        Transfer to: {node.data.department || node.data.phoneNumber}
                                      </p>
                                    )}
                                    {node.type === 'end' && (
                                      <p className="text-sm text-gray-600">{node.data.farewell}</p>
                                    )}
                                  </div>
                                </div>
                              </div>
                            ))}
                          </div>
                        </div>
                      </div>
                    </div>
                  )}
                </div>
              </>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};
