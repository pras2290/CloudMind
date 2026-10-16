import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { TooltipProvider } from "@radix-ui/react-tooltip";
import ChatPage from "./ChatPage";

type Handler = (url: string, init?: RequestInit) => { status: number; body?: unknown };

function mockFetch(handler: Handler) {
  const fn = vi.fn(async (url: string, init?: RequestInit) => {
    const { status, body } = handler(url, init);
    return new Response(body === undefined ? null : JSON.stringify(body), { status });
  });
  vi.stubGlobal("fetch", fn);
  return fn;
}

function renderChat() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <TooltipProvider>
        <MemoryRouter initialEntries={["/"]} future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
          <Routes>
            <Route path="/" element={<ChatPage />} />
            <Route path="/c/:sessionId" element={<ChatPage />} />
          </Routes>
        </MemoryRouter>
      </TooltipProvider>
    </QueryClientProvider>,
  );
}

const kb = { ready: true, total: 10, by_source: {}, last_refreshed: null, job: null };

beforeAll(() => {
  Element.prototype.scrollIntoView = vi.fn();
});
afterEach(() => vi.unstubAllGlobals());

describe("ChatPage", () => {
  it("sends on Enter and renders the answer with source and confidence", async () => {
    const fetchFn = mockFetch((url) => {
      if (url === "/api/kb/status") return { status: 200, body: kb };
      if (url === "/api/chat")
        return {
          status: 200,
          body: {
            session_id: "s1",
            answer: "You have **7** instances.",
            source: "aws_ec2",
            confidence: 0.82,
            docs: [{ source: "aws_ec2", type: "ec2", title: "i-123", snippet: "Name: web-0" }],
          },
        };
      return { status: 200, body: [] };
    });
    renderChat();
    const box = await screen.findByLabelText("Message");
    await userEvent.type(box, "how many EC2 instances{Enter}");

    expect(await screen.findByText("7")).toBeInTheDocument();
    expect(screen.getByText("EC2")).toBeInTheDocument();
    expect(screen.getByText("82%")).toBeInTheDocument();
    expect(screen.getByText("1 retrieved source")).toBeInTheDocument();
    const chatCall = fetchFn.mock.calls.find(([u]) => u === "/api/chat")!;
    expect(JSON.parse(chatCall[1]!.body as string).message).toBe("how many EC2 instances");
  });

  it("Shift+Enter inserts a newline instead of sending", async () => {
    const fetchFn = mockFetch(() => ({ status: 200, body: kb }));
    renderChat();
    const box = await screen.findByLabelText("Message");
    await userEvent.type(box, "line one{Shift>}{Enter}{/Shift}line two");
    expect(box).toHaveValue("line one\nline two");
    expect(fetchFn.mock.calls.some(([u]) => u === "/api/chat")).toBe(false);
  });

  it("shows the server error with a Retry that resends", async () => {
    let attempts = 0;
    mockFetch((url) => {
      if (url === "/api/kb/status") return { status: 200, body: kb };
      if (url === "/api/chat") {
        attempts += 1;
        return attempts === 1
          ? { status: 500, body: { detail: "Something went wrong, please try again." } }
          : { status: 200, body: { session_id: "s1", answer: "Recovered", source: "aws_s3", confidence: 0.5, docs: [] } };
      }
      return { status: 200, body: [] };
    });
    renderChat();
    await userEvent.type(await screen.findByLabelText("Message"), "list buckets{Enter}");
    expect(await screen.findByRole("alert")).toHaveTextContent("Something went wrong, please try again.");
    await userEvent.click(screen.getByRole("button", { name: /retry/i }));
    await waitFor(() => expect(screen.getByText("Recovered")).toBeInTheDocument());
    expect(attempts).toBe(2);
  });

  it("disables the composer when the knowledge base is empty", async () => {
    mockFetch(() => ({ status: 200, body: { ...kb, ready: false, total: 0 } }));
    renderChat();
    expect(await screen.findByText("Knowledge base is empty")).toBeInTheDocument();
    expect(screen.getByLabelText("Message")).toBeDisabled();
  });
});
