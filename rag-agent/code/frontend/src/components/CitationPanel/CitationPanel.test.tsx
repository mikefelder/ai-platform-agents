// Mock the imports
jest.mock("react-markdown", () => {
  return {
    __esModule: true,
    default: () => <div>ReactMarkdown Mock</div>,
  };
});

jest.mock("remark-gfm", () => {
  return {
    __esModule: true,
    default: () => <div>remarkGfm Mock</div>,
  };
});

jest.mock("rehype-raw", () => {
  return {
    __esModule: true,
    default: () => <div>rehypeRaw Mock</div>,
  };
});

// Your component import
import { render, screen, fireEvent } from "@testing-library/react";
import { CitationPanel, rewriteCitationUrl } from "./CitationPanel";


describe("CitationPanel", () => {

  const activeCitation = ["1", "2", "Sample Citation Content"];
  const setIsCitationPanelOpen = jest.fn();

  afterEach(() => {
    // Clear all mocks and cache
    jest.clearAllMocks();
    jest.resetModules();
  });

  test("renders CitationPanel with citation content", () => {
    render(
      <CitationPanel
        activeCitation={activeCitation}
        setIsCitationPanelOpen={setIsCitationPanelOpen}
      />
    );

    expect(screen.getByText("Citations")).toBeInTheDocument();
    expect(screen.getByText("Sample Citation Content")).toBeInTheDocument();
    expect(
      screen.getByText(
        "Tables, images, and other special formatting not shown in this preview. Please follow the link to review the original document."
      )
    ).toBeInTheDocument();
  });

  test("closes CitationPanel on click", () => {
    render(
      <CitationPanel
        activeCitation={activeCitation}
        setIsCitationPanelOpen={setIsCitationPanelOpen}
      />
    );
    fireEvent.click(screen.getByRole('button', { hidden: true }));
    expect(setIsCitationPanelOpen).toHaveBeenCalledWith(false);
  });

  test("closes CitationPanel on Enter key press", () => {
    render(
      <CitationPanel
        activeCitation={activeCitation}
        setIsCitationPanelOpen={setIsCitationPanelOpen}
      />
    );

    fireEvent.keyDown(screen.getByRole('button', { hidden: true }), { key: "Enter" });
    expect(setIsCitationPanelOpen).toHaveBeenCalledWith(false);
  });

  test("closes CitationPanel on Space key press", () => {
    render(
      <CitationPanel
        activeCitation={activeCitation}
        setIsCitationPanelOpen={setIsCitationPanelOpen}
      />
    );

    fireEvent.keyDown(screen.getByRole('button', { hidden: true }), { key: " " });
    expect(setIsCitationPanelOpen).toHaveBeenCalledWith(false);
  });

  test("Should not trigger setIsCitationPanelOpen other than Enter/Space key press", () => {
    ; setIsCitationPanelOpen.mockReturnValue(true)
    render(
      <CitationPanel
        activeCitation={activeCitation}
        setIsCitationPanelOpen={setIsCitationPanelOpen}
      />
    );
    fireEvent.keyDown(screen.getByRole('button', { hidden: true }), { key: "Escape" });
    expect(setIsCitationPanelOpen).not.toHaveBeenCalled()
  });

});

describe("rewriteCitationUrl", () => {
  test("rewrites a genuine blob.core.windows.net URL", () => {
    const markdown =
      "[doc](https://mystorageaccount.blob.core.windows.net/documents/filename.pdf)";
    const result = rewriteCitationUrl(markdown);
    expect(result).toBe("[doc](/api/files/filename.pdf)");
  });

  test("does not treat a malicious host containing blob.core.windows.net as trusted", () => {
    const markdown =
      "[doc](https://evil-example.com/blob.core.windows.net/documents/filename.pdf)";
    const result = rewriteCitationUrl(markdown);
    expect(result).toBe(
      "[doc](https://evil-example.com/blob.core.windows.net/documents/filename.pdf)"
    );
  });

  test("does not treat a host with blob.core.windows.net as a suffix-lookalike as trusted", () => {
    const markdown =
      "[doc](https://evilblob.core.windows.net.evil.com/documents/filename.pdf)";
    const result = rewriteCitationUrl(markdown);
    expect(result).toBe(
      "[doc](https://evilblob.core.windows.net.evil.com/documents/filename.pdf)"
    );
  });
});
