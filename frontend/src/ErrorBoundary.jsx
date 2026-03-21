import { Component } from 'react';

class ErrorBoundary extends Component {
    constructor(props) {
        super(props);
        this.state = { hasError: false, error: null };
    }

    static getDerivedStateFromError(error) {
        return { hasError: true, error };
    }

    componentDidCatch(error, info) {
        console.error('[ErrorBoundary] React render crash:', error, info.componentStack);
    }

    render() {
        if (this.state.hasError) {
            return (
                <div style={{
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    height: '100vh',
                    flexDirection: 'column',
                    fontFamily: "'Inter', system-ui, sans-serif",
                    gap: '16px',
                    padding: '40px',
                    textAlign: 'center',
                }}>
                    <h2 style={{ fontSize: '20px', fontWeight: 700, margin: 0 }}>Something went wrong</h2>
                    <p style={{ color: '#666', maxWidth: 480, lineHeight: 1.6 }}>
                        The app hit an unexpected error while rendering. Check the browser console for details.
                    </p>
                    <pre style={{
                        background: '#f5f5f5',
                        padding: '16px',
                        borderRadius: '8px',
                        fontSize: '12px',
                        maxWidth: '600px',
                        overflow: 'auto',
                        color: '#c00',
                    }}>
                        {this.state.error?.message || 'Unknown error'}
                    </pre>
                    <button
                        onClick={() => this.setState({ hasError: false, error: null })}
                        style={{
                            padding: '10px 24px',
                            background: '#0061FF',
                            color: '#fff',
                            border: 'none',
                            borderRadius: '6px',
                            cursor: 'pointer',
                            fontSize: '13px',
                            fontWeight: 600,
                        }}
                    >
                        Retry
                    </button>
                </div>
            );
        }

        return this.props.children;
    }
}

export default ErrorBoundary;
