// header.js (must be in /static/js/)

function Header() {
  return (
    <nav className="navbar navbar-expand-lg navbar-dark bg-dark mb-4">
      <div className="container-fluid">
        <a className="navbar-brand" href="/">📈 Trade Tracker</a>
            <button
              className="navbar-toggler"
              type="button"
              data-bs-toggle="collapse"
              data-bs-target="#navbarNav"
              aria-controls="navbarNav"
              aria-expanded="false"
              aria-label="Toggle navigation">
              <span className="navbar-toggler-icon"></span>
            </button>
        <div className="collapse navbar-collapse" id="navbarNav">    
          <ul className="navbar-nav ms-auto">
            <li className="nav-item"><a className="nav-link" href="/add_trade">Add</a></li>
            <li className="nav-item"><a className="nav-link" href="/edit_trade">Edit</a></li>
            <li className="nav-item"><a className="nav-link" href="/delete_trade">Delete</a></li>
            <li className="nav-item"><a className="nav-link" href="/report">Report</a></li>
          </ul>
        </div>
      </div>
    </nav>
  );
}

ReactDOM.createRoot(document.getElementById("react-header")).render(<Header />);
