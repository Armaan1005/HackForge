// Fail safely in the UI too: an unexpected error in one page shows a calm message with a way out,
// instead of a blank screen. Resets when you navigate to another page.
import { Component, type ReactNode } from 'react';

export class ErrorBoundary extends Component<{ children: ReactNode; resetKey?: string }, { error: Error | null }> {
  state = { error: null as Error | null };
  static getDerivedStateFromError(error: Error) { return { error }; }
  componentDidCatch(error: Error) { console.error('Page error caught by ErrorBoundary:', error); }
  componentDidUpdate(prev: { resetKey?: string }) { if (prev.resetKey !== this.props.resetKey && this.state.error) this.setState({ error: null }); }
  render() {
    if (!this.state.error) return this.props.children;
    return (
      <div className="card" style={{ maxWidth: 560, margin: '40px auto', textAlign: 'center' }}>
        <h2>This page hit a problem</h2>
        <p className="muted" style={{ margin: '8px 0 16px' }}>Nothing was changed: no decision was recorded and no payment was touched. Reload to try again, or go back to Home.</p>
        <div className="row-flex" style={{ justifyContent: 'center' }}>
          <button type="button" className="btn btn-primary btn-sm" onClick={() => location.reload()}>Reload</button>
          <a className="btn btn-secondary btn-sm" href="/home">Go to Home</a>
        </div>
      </div>
    );
  }
}
