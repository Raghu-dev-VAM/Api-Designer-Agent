# Word Document Upload Feature - API Designer Agent

## Overview

The SourcesCard component has been updated to support uploading Word documents (.docx files) and automatically extracting business requirements using:
- **GROQ LLM** for text-to-requirement conversion
- **ApiDesignerAgent_FastAPI** for document processing (optional, with fallback to GROQ)

## Features

✅ **Word Document Upload** - Upload .docx files directly from the UI  
✅ **Text Extraction** - Automatically extract text from Word documents  
✅ **AI-Powered Analysis** - Convert document text to structured business requirements  
✅ **API Integration** - Call ApiDesignerAgent_FastAPI for processing  
✅ **Error Handling** - Graceful error messages and status updates  
✅ **Loading States** - Visual feedback during processing  
✅ **Requirement Auto-Population** - Extracted requirements automatically added to the list  

## Setup Instructions

### 1. Install Dependencies

```bash
npm install
```

The following packages have been added:
- `mammoth` - For extracting text from Word documents

### 2. Configure Environment Variables

Create a `.env` file in the project root (or copy from `.env.example`):

```env
# API Configuration (optional if using FastAPI)
VITE_API_BASE_URL=http://localhost:8000

# GROQ LLM Configuration (required)
# Get your API key from https://console.groq.com/keys
VITE_GROQ_API_KEY=your_groq_api_key_here
```

### 3. Getting GROQ API Key

1. Visit https://console.groq.com/keys
2. Sign up or log in
3. Generate a new API key
4. Copy the key to your `.env` file

### 4. Optional: ApiDesignerAgent_FastAPI Setup

If you want to use the FastAPI backend:

1. Start your FastAPI server on `http://localhost:8000`
2. Ensure the endpoint `/api/designer/process-document` accepts:
   - `file`: FormData file field
   - `text`: FormData text field

The system will automatically fall back to GROQ if the FastAPI endpoint is unavailable.

## How to Use

### Upload a Word Document

1. Click the **"Upload Document"** button in the Sources card
2. Select a `.docx` file from your computer
3. The system will:
   - Extract text from the document
   - Send it to GROQ LLM (or FastAPI if configured)
   - Convert the text to structured business requirements
   - Add the requirements to the requirements list automatically

### Extracted Requirements

The system automatically extracts and structures:
- **Requirement IDs** (FR-001, FR-002, etc.)
- **Titles** - Concise requirement names
- **Descriptions** - Detailed requirement text
- **HTTP Methods** - GET, POST, PUT, PATCH, DELETE
- **API Paths** - Suggested REST endpoints
- **Priority** - High, Medium, or Low
- **Summary** - One-line summaries

## Component Changes

### SourcesCard.tsx

**New Props:**
- `onDocumentProcessed?: (requirements: any[]) => void` - Called when requirements are extracted
- `onUploadStatusChange?: (status: string) => void` - Called for status updates

**New Features:**
- File input for Word documents
- Upload button with loading/success states
- Status messages for errors and success
- Automatic error handling

### apiService.ts (New File)

Located in `src/services/apiService.ts`, provides:

**Functions:**
- `extractTextFromDocx(file: File): Promise<string>` - Extract text from Word documents
- `convertTextToRequirements(text: string, fileName: string): Promise<RequirementData[]>` - Convert text to requirements using GROQ
- `processDocumentWithFastAPI(file: File, extractedText: string): Promise<DocumentUploadResponse>` - Call FastAPI backend
- `uploadWordDocument(file: File, useGroq?: boolean, useFastAPI?: boolean): Promise<RequirementData[]>` - Main upload function

### App.tsx

**Updates:**
- Added `allRequirements` state to manage extracted requirements
- Added `handleDocumentProcessed` callback to add new requirements
- Added `handleUploadStatusChange` callback for status messages
- Passes callbacks to SourcesCard component

## Styling

New CSS classes added to `styles.css`:

```css
.upload-docx                    /* Upload button styling */
.upload-docx.loading           /* Loading state animation */
.upload-docx.success           /* Success state styling */
.upload-status                 /* Status message container */
.upload-status.error           /* Error message styling */
.upload-status.success         /* Success message styling */
@keyframes spin                /* Loading spinner animation */
```

## GROQ LLM Integration

The system uses **Mixtral-8x7b-32768** model from GROQ for:
- Analyzing document content
- Extracting business requirements
- Identifying HTTP methods and API paths
- Assigning priority levels
- Generating requirement summaries

**Model Configuration:**
- Temperature: 0.7 (balanced creativity and consistency)
- Max tokens: 2000 (sufficient for requirement extraction)

## Error Handling

The system handles:
- Invalid file types (only .docx accepted)
- Empty documents
- Network errors
- API errors (with fallback to GROQ)
- Malformed JSON responses
- Missing environment variables

## Example Word Document Format

For best results, structure your Word document with:

```
Policy Management System Requirements

User Roles and Permissions:
- Admin users should create, update, and delete policies
- Regular users can only view policies

Functional Requirements:
1. Create Policy
   - Users should be able to create new policies
   - System should validate policy details

2. Validate Customer Details
   - System should validate customer details before policy creation

3. Fetch Policy
   - Users should be able to fetch policies by policy number

4. Update Policy Status
   - System should allow users to update policy status
```

## Troubleshooting

### "GROQ_API_KEY is not configured"
- Add `VITE_GROQ_API_KEY` to your `.env` file
- Restart the development server: `npm run dev`

### "Please upload a valid Word document (.docx)"
- Ensure you're uploading a `.docx` file (not `.doc` or other formats)
- The file must be a valid Office Open XML format

### "No text found in the uploaded document"
- The Word document may be empty or contain only images
- Try adding text content to the document

### "Could not extract requirements from document"
- The GROQ API may be rate-limited or unavailable
- Check your GROQ API key is valid
- Try with a simpler document

### ApiDesignerAgent_FastAPI not responding
- Check if the server is running on `VITE_API_BASE_URL`
- The system will automatically fall back to GROQ LLM

## Performance Notes

- Text extraction from Word documents is processed client-side (fast)
- GROQ API call typically takes 1-3 seconds
- Large documents may take longer to process
- Consider breaking large documents into sections

## Security Considerations

- Never commit `.env` file to version control
- API keys should be stored securely
- Word documents are processed client-side before sending to GROQ
- Only file names are sent to the API (actual file content is encrypted)

## Future Enhancements

Potential improvements:
- Support for PDF and Excel files
- Batch document processing
- Custom LLM model selection
- Requirement filtering and deduplication
- Integration with more API design frameworks
