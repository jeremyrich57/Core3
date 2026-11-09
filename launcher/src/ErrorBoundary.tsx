import { Component, type ErrorInfo, type ReactNode } from "react";

/** Shows a render crash instead of leaving the window blank. */
export default class ErrorBoundary extends Component<{ children: ReactNode }, { error: Error | null }> {
  state = { error: null as Error | null };

  static getDerivedStateFromError(error: Error) {
    return { error };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error(error, info.componentStack);
  }

  render() {
    if (!this.state.error) return this.props.children;
    return (
      <main className="app crashed">
        <h1>Something went wrong</h1>
        <pre>{this.state.error.message}</pre>
        <button onClick={() => window.location.reload()}>Reload</button>
      </main>
    );
  }
}
