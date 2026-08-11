import { DocPage, docMetadata } from '@/components/docs/DocPage'
import { CodeBlock } from '@/components/docs/CodeBlock'
import { Chain, Figure } from '@/components/docs/Diagram'
import {
  A, C, Callout, H2, H3, LI, P, ParamTable, Step, Steps, Strong, Table, UL,
} from '@/components/docs/prose'

export const metadata = docMetadata('/docs/knowledge-base')

export default function KnowledgeBasePage() {
  return (
    <DocPage href="/docs/knowledge-base">
      <H2 id="how-rag-works">How retrieval works</H2>
      <P>
        A knowledge base lets an agent answer from your documents instead of from the
        model&rsquo;s training data or a bloated prompt. The technique is retrieval-augmented
        generation, and understanding the pipeline explains every setting on this page.
      </P>

      <Figure caption="Documents are chunked and embedded once, at upload. Retrieval happens per question, at call time.">
        <Chain
          stages={[
            { label: 'Document', caption: 'PDF, text, URL', tone: 'slate' },
            { label: 'Chunks', caption: 'split by size', tone: 'blue' },
            { label: 'Embeddings', caption: 'vectors', tone: 'violet' },
            { label: 'Search', caption: 'per question', tone: 'amber' },
            { label: 'Answer', caption: 'model + passages', tone: 'brand' },
          ]}
        />
      </Figure>

      <P>The consequences of that pipeline are worth stating plainly:</P>
      <UL>
        <LI>
          <Strong>The agent only sees the retrieved chunks</Strong>, not the whole document. If
          the answer is split across two chunks that do not both surface, it will not be found.
        </LI>
        <LI>
          <Strong>Retrieval is by meaning, not keyword.</Strong> A caller asking &ldquo;can I
          send it back?&rdquo; will match a passage about returns, even without the word
          &ldquo;return&rdquo;.
        </LI>
        <LI>
          <Strong>Chunking happens at upload.</Strong> Changing chunk settings later does not
          re-chunk existing documents — they must be re-uploaded.
        </LI>
      </UL>

      <H2 id="creating-a-kb">Creating a knowledge base</H2>
      <Steps>
        <Step n={1} title="Create it">
          <P>
            <Strong>Knowledge Base</Strong> → <Strong>New Knowledge Base</Strong>. Name it for
            its contents — <C>Returns &amp; Refunds Policy</C>, not <C>KB 2</C>.
          </P>
        </Step>
        <Step n={2} title="Set chunking, if the defaults do not fit">
          <P>The defaults suit prose. See <A href="#chunking">chunking</A>.</P>
        </Step>
        <Step n={3} title="Add documents">
          <P>Upload files, paste text, or point at a URL.</P>
        </Step>
        <Step n={4} title="Wait for processing">
          <P>Each document is chunked and embedded. Large files take a moment.</P>
        </Step>
        <Step n={5} title="Test retrieval">
          <P>Search it with real caller questions before wiring it to an agent.</P>
        </Step>
        <Step n={6} title="Connect it to an agent">
          <P>With settings appropriate to how central this knowledge is.</P>
        </Step>
      </Steps>

      <Callout kind="tip" title="Several small bases beat one large one">
        Separate knowledge bases per subject let you tune retrieval per subject and attach
        only what a given agent needs. One base holding everything means every question
        searches everything, and precision suffers.
      </Callout>

      <H2 id="chunking">Chunking settings</H2>
      <ParamTable
        params={[
          {
            name: 'chunk_size',
            type: 'characters',
            default: '1000',
            description: (
              <>
                How much text goes in each chunk. Smaller is more precise but risks splitting
                an answer; larger keeps context together but dilutes the match.
              </>
            ),
          },
          {
            name: 'chunk_overlap',
            type: 'characters',
            default: '200',
            description: (
              <>
                How much each chunk repeats from the previous one. Overlap is what stops an
                answer being lost at a boundary. Roughly 15–25% of chunk size works well.
              </>
            ),
          },
          {
            name: 'embedding_model',
            type: 'string',
            default: 'text-embedding-ada-002',
            description: (
              <>
                The model that turns text into vectors. Must stay consistent within a
                knowledge base — vectors from different models are not comparable.
              </>
            ),
          },
          {
            name: 'vector_dimension',
            type: 'number',
            default: '1536',
            description: 'Determined by the embedding model. Rarely changed by hand.',
          },
          {
            name: 'vector_store_type',
            type: 'enum',
            default: 'pinecone',
            description: (
              <>
                Where vectors live. The default path stores them in the database, so semantic
                search works with no external service to run.
              </>
            ),
          },
        ]}
      />

      <Table
        headers={['Content', 'Chunk size', 'Overlap', 'Why']}
        widths={['w-[28%]', 'w-[16%]', 'w-[14%]']}
        rows={[
          ['FAQ — short Q&A pairs', '500', '100', 'Each answer is self-contained; keep chunks tight.'],
          ['Policy or manual prose', '1000', '200', 'The default. Balances precision and context.'],
          ['Technical documentation', '1500', '300', 'Answers need surrounding explanation to make sense.'],
          ['Product listings', '300', '50', 'Each item is independent; small chunks stop products bleeding together.'],
        ]}
      />

      <Callout kind="warning" title="Changing chunking is retroactive only on re-upload">
        Existing documents keep the chunks they were created with. To apply new settings,
        delete and re-upload.
      </Callout>

      <H2 id="adding-documents">Adding documents</H2>
      <Table
        headers={['Source', 'Use for']}
        widths={['w-[20%]']}
        rows={[
          [<C>file</C>, 'PDFs, Word documents, text files, HTML. Uploaded directly.'],
          [<C>url</C>, 'A web page, fetched and extracted.'],
          [<C>text</C>, 'Pasted text. Fastest way to add a policy or a set of FAQs.'],
          [<C>api</C>, 'Documents pushed programmatically from your own systems.'],
        ]}
      />
      <P>Each document records:</P>
      <ParamTable
        params={[
          { name: 'title', type: 'string', required: true, description: 'Shown in the document list and returned with search results.' },
          { name: 'content', type: 'text', required: true, description: 'The extracted text. This is what gets chunked.' },
          { name: 'content_hash', type: 'sha-256', description: 'Used to deduplicate — uploading the same document twice does not double your chunks.' },
          { name: 'language', type: 'locale', default: 'en', description: 'The document language.' },
          { name: 'document_metadata', type: 'object', description: 'Your own fields — author, effective date, department — carried through to results.' },
          { name: 'total_chunks', type: 'number', description: 'How many chunks it produced. Zero after processing means extraction failed.' },
        ]}
      />

      <H2 id="processing">Processing status</H2>
      <Table
        headers={['Status', 'Meaning']}
        widths={['w-[20%]']}
        rows={[
          [<C>pending</C>, 'Queued.'],
          [<C>processing</C>, 'Being chunked and embedded.'],
          [<C>completed</C>, 'Searchable.'],
          [<C>failed</C>, <>Something went wrong; <C>processing_error</C> says what.</>],
        ]}
      />
      <P>The usual causes of a failure:</P>
      <UL>
        <LI><Strong>A scanned PDF</Strong> — images of text, with no text layer to extract. Run OCR first.</LI>
        <LI><Strong>A password-protected file</Strong> — remove protection before uploading.</LI>
        <LI><Strong>An unreachable URL</Strong> — behind a login, or blocking automated fetches.</LI>
        <LI><Strong>An empty document</Strong> — extraction found nothing.</LI>
      </UL>
      <Callout kind="tip" title="Check total_chunks after upload">
        A document that reports <C>completed</C> with zero chunks contributed nothing. That is
        the quiet failure mode worth watching for.
      </Callout>

      <H2 id="connecting-to-agents">Connecting to an agent</H2>
      <P>
        Link a knowledge base on the agent&rsquo;s <Strong>Knowledge</Strong> tab. The link is
        many-to-many with its own settings, so the same base can serve several agents
        differently.
      </P>

      <H2 id="link-settings">Link settings reference</H2>
      <ParamTable
        params={[
          {
            name: 'priority',
            type: 'number',
            default: '0',
            description: (
              <>
                Higher is searched first. Use it when one base should win — put an official
                policy above a general FAQ that might paraphrase it.
              </>
            ),
          },
          {
            name: 'max_results',
            type: 'number',
            default: '5',
            description: (
              <>
                How many chunks to retrieve. More context but a longer, slower, costlier
                prompt. Three to five suits most agents; raise it only if answers are
                arriving incomplete.
              </>
            ),
          },
          {
            name: 'min_similarity',
            type: 'number 0–1',
            default: '0.7',
            description: (
              <>
                The relevance floor. Below it, a chunk is not returned at all. Raise toward{' '}
                <C>0.8</C> to stop loosely-related passages leaking in; lower toward{' '}
                <C>0.6</C> if the agent claims not to know things that are plainly documented.
              </>
            ),
          },
          {
            name: 'auto_inject',
            type: 'boolean',
            default: 'true',
            description: (
              <>
                When on, relevant passages are added to the model&rsquo;s context
                automatically. When off, the agent must reach the base through a{' '}
                <A href="/docs/tools/assistant#query-knowledge-base">Query Knowledge Base
                tool</A>.
              </>
            ),
          },
          {
            name: 'is_active',
            type: 'boolean',
            default: 'true',
            description: 'Switch the link off without removing it.',
          },
        ]}
      />

      <Callout kind="note" title="Tuning min_similarity is the main lever">
        Almost every retrieval complaint resolves here. &ldquo;It answers with irrelevant
        information&rdquo; → raise it. &ldquo;It says it does not know things that are in the
        documents&rdquo; → lower it. Change it in steps of <C>0.05</C> and re-test with the
        same questions.
      </Callout>

      <H2 id="testing-retrieval">Testing retrieval</H2>
      <P>
        Search a knowledge base directly, without going through an agent. This isolates
        retrieval from the model&rsquo;s behaviour, which is the only way to tell which of the
        two is at fault.
      </P>
      <UL>
        <LI>Use questions in the words a caller would use, not the words in your document.</LI>
        <LI>Check the similarity scores — consistently near your floor means the content does not really address the question.</LI>
        <LI>Try the questions your agent has already got wrong. The transcripts in <A href="/docs/calls">Calls</A> are a ready-made test set.</LI>
      </UL>
      <P>
        Searches are logged with their scores and timing, so you can see over time what people
        ask and where retrieval is weak.
      </P>

      <H2 id="writing-for-retrieval">Writing documents for retrieval</H2>
      <P>
        Documents written for humans to read linearly often retrieve badly. Small changes make
        a large difference.
      </P>

      <H3>Make each section self-contained</H3>
      <P>
        A chunk is retrieved alone. A paragraph beginning &ldquo;As mentioned above, this also
        applies to&hellip;&rdquo; is useless without the paragraph above it. Restate the
        subject.
      </P>
      <CodeBlock
        language="Before and after"
        code={`✗  As noted, the same window applies to sale items.

✓  Sale items may also be returned within 30 days of purchase,
   provided they are unworn and have their original tags.`}
      />

      <H3>Use the caller&rsquo;s vocabulary</H3>
      <P>
        Internal terms do not match how people ask. If customers say &ldquo;send it back&rdquo;
        and your document says &ldquo;initiate an RMA&rdquo;, include both.
      </P>

      <H3>Lead with the answer</H3>
      <P>
        Put the fact in the first sentence of a section, with the caveats after. Retrieval
        favours passages where the answer is prominent, and so does a model summarising under
        time pressure.
      </P>

      <H3>Keep it current</H3>
      <P>
        A knowledge base is only as good as its freshest document. Stale prices and withdrawn
        policies get quoted confidently to real customers. Replace documents rather than
        appending corrections.
      </P>

      <Callout kind="tip" title="Prompt or knowledge base?">
        Behaviour belongs in the <A href="/docs/agents/configuration#prompt">system prompt</A>{' '}
        — how to speak, what to refuse, when to escalate. Facts belong here — prices, hours,
        policies, product details. Facts in a prompt need re-testing every time they change;
        facts here are updated by swapping a document.
      </Callout>
    </DocPage>
  )
}
