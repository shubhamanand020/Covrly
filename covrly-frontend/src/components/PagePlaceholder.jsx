function PagePlaceholder({ title, routePath }) {
  return (
    <section className="page">
      <section className="page-card">
        <p className="page-path">{routePath}</p>
        <h1>{title}</h1>
        <p className="page-copy">Placeholder page for {title.toLowerCase()}.</p>
      </section>
    </section>
  )
}

export default PagePlaceholder