// header.js (must be in /static/js/)

function Header() {
  return (
    <nav className="navbar navbar-expand-lg navbar-dark bg-dark mb-4">
      <div className="container-fluid">
        <a className="navbar-brand" href="/">📈 Trade Tracker</a>
        <ul className="navbar-nav">
          <li className="nav-item"><a className="nav-link" href="/add_trade">Add</a></li>
          <li className="nav-item"><a className="nav-link" href="/edit_trade">Edit</a></li>
          <li className="nav-item"><a className="nav-link" href="/delete_trade">Delete</a></li>
          <li className="nav-item"><a className="nav-link" href="/report">Report</a></li>
        </ul>
      </div>
    </nav>
  );
}

ReactDOM.createRoot(document.getElementById("react-header")).render(<Header />);
