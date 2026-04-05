# create_rag_database.R
# Script to create and populate a SQLite database for RAG queries

library(DBI)
library(RSQLite)

# Path to the database file
DB_PATH <- "06_rag/data/rag_example.db"

# Remove existing database if it exists
if(file.exists(DB_PATH)) {
  file.remove(DB_PATH)
}

# Create connection
con <- dbConnect(RSQLite::SQLite(), DB_PATH)

# Create documents table
dbExecute(con, "
CREATE TABLE documents (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  title TEXT NOT NULL,
  content TEXT NOT NULL,
  category TEXT,
  author TEXT,
  created_date TEXT,
  tags TEXT,
  source_url TEXT
)
")

# Create index on category and title for faster searches
dbExecute(con, "CREATE INDEX idx_category ON documents(category)")
dbExecute(con, "CREATE INDEX idx_title ON documents(title)")

# Sample documents for RAG queries
documents <- data.frame(
  title = c(
    "Introduction to Machine Learning",
    "Python Best Practices",
    "R Data Analysis Workflow",
    "SQL Query Optimization",
    "Docker Container Basics",
    "API Design Principles",
    "Version Control with Git",
    "Database Normalization",
    "Statistical Hypothesis Testing",
    "Web Scraping Ethics"
  ),
  content = c(
    "Machine learning is a subset of artificial intelligence that enables systems to learn and improve from experience without being explicitly programmed. It uses algorithms to analyze data, identify patterns, and make predictions or decisions. Common types include supervised learning (using labeled data), unsupervised learning (finding patterns in unlabeled data), and reinforcement learning (learning through trial and error with rewards). Popular algorithms include linear regression, decision trees, neural networks, and support vector machines. Applications range from recommendation systems and image recognition to natural language processing and autonomous vehicles.",
    
    "Python best practices include writing clean, readable code following PEP 8 style guidelines. Use meaningful variable names, write docstrings for functions and classes, and organize code into modules. Implement error handling with try-except blocks, use list comprehensions for simple transformations, and prefer built-in functions over custom implementations when possible. Always use virtual environments to manage dependencies, write unit tests for critical functions, and use type hints for better code documentation. Follow the DRY (Don't Repeat Yourself) principle and keep functions focused on a single responsibility.",
    
    "R data analysis workflow typically begins with data import using functions like read.csv(), read_excel(), or database connections. Next, explore the data using summary(), str(), and head() functions. Clean the data by handling missing values, removing duplicates, and transforming variables. Perform exploratory data analysis with visualization using ggplot2 or base R plotting. Apply statistical tests or build models as needed. Document your analysis with R Markdown to create reproducible reports. Use packages like dplyr for data manipulation, tidyr for data tidying, and ggplot2 for visualization.",
    
    "SQL query optimization involves several strategies to improve performance. Use indexes on frequently queried columns, especially foreign keys and columns in WHERE clauses. Avoid SELECT * and only retrieve needed columns. Use JOINs instead of subqueries when possible, as they're often more efficient. Filter data early with WHERE clauses before joining tables. Use EXPLAIN or EXPLAIN ANALYZE to understand query execution plans. Consider partitioning large tables, use appropriate data types to reduce storage, and update table statistics regularly. For complex queries, consider materialized views or denormalization where appropriate.",
    
    "Docker containers package applications with their dependencies into portable, isolated environments. Containers are lightweight compared to virtual machines because they share the host OS kernel. Key concepts include images (read-only templates), containers (running instances of images), and Dockerfiles (instructions to build images). Common commands include docker build to create images, docker run to start containers, docker ps to list running containers, and docker-compose to manage multi-container applications. Containers enable consistent deployments across development, testing, and production environments, making DevOps workflows more reliable.",
    
    "API design principles emphasize RESTful architecture with clear, consistent endpoints. Use HTTP methods appropriately: GET for retrieval, POST for creation, PUT for full updates, PATCH for partial updates, DELETE for removal. Design URLs that are intuitive and hierarchical, use proper HTTP status codes, and return consistent JSON responses. Implement versioning (e.g., /api/v1/) to maintain backward compatibility. Include pagination for list endpoints, use query parameters for filtering and sorting, and provide comprehensive error messages. Document APIs thoroughly with OpenAPI/Swagger specifications. Consider rate limiting, authentication, and CORS policies for security.",
    
    "Version control with Git enables tracking changes to code over time. Key concepts include repositories (local and remote), commits (snapshots of changes), branches (parallel development lines), and merges (combining branches). Common workflows include creating feature branches for new work, committing changes frequently with descriptive messages, and pushing to remote repositories like GitHub. Use git status to check file states, git add to stage changes, git commit to save snapshots, and git push to upload to remote. Resolve merge conflicts by editing conflicted files, then staging and committing. Use .gitignore to exclude files from version control.",
    
    "Database normalization reduces data redundancy and improves data integrity through a series of normal forms. First Normal Form (1NF) requires atomic values and no repeating groups. Second Normal Form (2NF) builds on 1NF and eliminates partial dependencies by ensuring non-key attributes depend on the entire primary key. Third Normal Form (3NF) eliminates transitive dependencies where non-key attributes depend on other non-key attributes. Higher normal forms (BCNF, 4NF, 5NF) address more complex dependencies. While normalization reduces redundancy, it may require more JOINs, so denormalization is sometimes used for performance optimization in read-heavy applications.",
    
    "Statistical hypothesis testing involves formulating null and alternative hypotheses, selecting an appropriate test based on data characteristics, calculating a test statistic, and comparing it to a critical value or p-value. Common tests include t-tests for comparing means, chi-square tests for categorical data, ANOVA for comparing multiple groups, and regression analysis for relationships. The significance level (alpha, typically 0.05) determines the threshold for rejecting the null hypothesis. Type I errors occur when we reject a true null hypothesis, while Type II errors occur when we fail to reject a false null hypothesis. Effect size measures the practical significance of findings beyond statistical significance.",
    
    "Web scraping ethics involve respecting website terms of service, robots.txt files, and rate limiting to avoid overloading servers. Always check if a website provides an API as a preferred alternative. Use appropriate delays between requests, respect copyright and intellectual property, and only scrape publicly available data. Consider the purpose of scraping: research and personal use are generally more acceptable than commercial use without permission. Be transparent about your scraping activities, handle data responsibly, and comply with data protection regulations like GDPR. Some websites explicitly prohibit scraping in their terms of service, which should be respected."
  ),
  category = c(
    "Machine Learning",
    "Programming",
    "Data Analysis",
    "Database",
    "DevOps",
    "API Development",
    "Version Control",
    "Database",
    "Statistics",
    "Web Development"
  ),
  author = c(
    "Dr. Sarah Chen",
    "Alexandra Martinez",
    "Dr. Sarah Chen",
    "Jordan Kim",
    "Alexandra Martinez",
    "Jordan Kim",
    "Alexandra Martinez",
    "Jordan Kim",
    "Dr. Sarah Chen",
    "Alexandra Martinez"
  ),
  created_date = c(
    "2024-01-15",
    "2024-02-03",
    "2024-01-20",
    "2024-02-10",
    "2024-01-28",
    "2024-02-15",
    "2024-01-25",
    "2024-02-08",
    "2024-01-18",
    "2024-02-12"
  ),
  tags = c(
    "AI, algorithms, supervised learning, neural networks",
    "python, coding standards, PEP 8, best practices",
    "R, data science, visualization, tidyverse",
    "SQL, performance, indexing, optimization",
    "containers, virtualization, deployment, DevOps",
    "REST, HTTP, endpoints, API design",
    "git, version control, collaboration, branching",
    "database design, normalization, schema",
    "statistics, hypothesis testing, p-values",
    "scraping, ethics, data collection, robots.txt"
  ),
  source_url = c(
    "https://example.com/ml-intro",
    "https://example.com/python-best-practices",
    "https://example.com/r-workflow",
    "https://example.com/sql-optimization",
    "https://example.com/docker-basics",
    "https://example.com/api-design",
    "https://example.com/git-guide",
    "https://example.com/normalization",
    "https://example.com/hypothesis-testing",
    "https://example.com/scraping-ethics"
  ),
  stringsAsFactors = FALSE
)

# Insert documents into database
dbWriteTable(con, "documents", documents, append = TRUE, row.names = FALSE)

# Verify insertion
cat("Created database with", dbGetQuery(con, "SELECT COUNT(*) as count FROM documents")$count, "documents\n")

# Show sample query
cat("\nSample query results:\n")
print(dbGetQuery(con, "SELECT title, category FROM documents LIMIT 5"))

# Close connection
dbDisconnect(con)

cat("\nDatabase created successfully at:", DB_PATH, "\n")
