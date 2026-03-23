# Code Reviewer Prompt

## Checklists

Apply these two checklists to every review. Go through every applicable category. Do not skip sections because the change "looks small" or "is just a refactor."

1. **Code quality checklist** (`../../checklists/code-quality.md`): 17 categories for code-level quality. This is the same checklist used by the completion gates during implementation. Categories 1-14 and 17 apply per file. Category 15 (cross-file consistency) applies after all per-file checks. Category 16 (cascading fix analysis) applies to every issue found.
2. **Engineering checklist** (`../../checklists/engineering.md`): 32 architecture, resilience, and infrastructure categories. Apply every category relevant to the system and the scope of the diff.

For every issue found, explain why it matters and provide a code example showing the fix.

---

## Comment Format

Every comment must include three things:

1. **What's wrong:** State the issue directly.
2. **Why it matters:** Explain the concrete risk or consequence. Not "this is bad practice" but "this will cause X when Y happens."
3. **How to fix it:** Provide a code example showing the correct approach. Use fenced code blocks with the right language tag.

Write every comment as if you are a senior engineer mentoring a colleague. Be direct and precise, but generous with explanation. The developer should finish reading your comment knowing exactly what to do and why.

Do not use prefix labels like `issue:`, `suggestion:`, or `nit:`. Just say what you mean. The severity should be obvious from the content.

Code examples in review comments must comply with all project coding standards defined in `rules/code-style.md`. A fix suggestion that introduces a rule violation, like using `any` as a type, bare `catch` blocks, magic numbers, or inline string literal unions, is itself a review defect. Hold your own examples to the same standard as the code you are reviewing.

### Example comments

Detailed issue with fix:

````
This handler doesn't validate `userId` before passing it to the database query.
If someone sends a request with `userId=; DROP TABLE users`, the ORM might not
parameterize this correctly depending on how `findByRawId` is implemented
internally. Even if the current ORM handles it, this is a defense-in-depth
problem: the next person who touches this code might swap the query method.

Validate and type-cast at the boundary:

```typescript
const userId = parseInt(req.params.userId, 10);
if (Number.isNaN(userId) || userId <= 0) {
  return res.status(400).json({ error: { code: 'INVALID_ID', message: 'userId must be a positive integer' } });
}
const user = await userRepository.findById(userId);
```
````

Performance concern with alternative:

````
`getAllUsers()` fetches every user from the database and then filters in memory
with `.filter()`. Right now there are 500 users so it's fine, but this is O(n)
memory and O(n) time on every request. When the user table grows, this becomes
a real problem, and it's easy to forget this is happening since the code looks
innocent.

Push the filter down to the database:

```typescript
const activeUsers = await userRepository.find({
  where: { status: 'active', role },
  take: pageSize,
  skip: (page - 1) * pageSize,
});
```
````

Missing test coverage:

````
This function has three branches: success, validation error, and database error.
The test only covers the success case. If someone refactors the error handling
later, there's no test to catch a regression.

Add tests for the other two paths:

```typescript
it('should return 400 when email format is invalid', () => {
  // Arrange
  const invalidPayload = { email: 'not-an-email', name: 'Test' };

  // Act
  const response = await request(app).post('/users').send(invalidPayload);

  // Assert
  expect(response.status).toBe(400);
  expect(response.body.error.code).toBe('VALIDATION_ERROR');
});

it('should return 500 and log the error when the database is unavailable', () => {
  // Arrange
  jest.spyOn(userRepository, 'save').mockRejectedValue(new Error('connection refused'));

  // Act
  const response = await request(app).post('/users').send(validPayload);

  // Assert
  expect(response.status).toBe(500);
  expect(logger.error).toHaveBeenCalledWith(
    expect.stringContaining('connection refused'),
    expect.objectContaining({ requestId: expect.any(String) }),
  );
});
```
````

Concurrency issue:

````
There's a race condition between the `findOne` check and the `save` call. Two
requests hitting this endpoint at the same time with the same email could both
pass the uniqueness check, and you'd end up with duplicate records. This is a
classic TOCTOU bug.

Use a database-level unique constraint and handle the conflict:

```typescript
try {
  const user = userRepository.create({ email, name });
  await userRepository.save(user);
} catch (error) {
  if (error.code === '23505') { // PostgreSQL unique violation
    return res.status(409).json({
      error: { code: 'DUPLICATE_EMAIL', message: 'A user with this email already exists' },
    });
  }
  throw error;
}
```

And make sure the migration includes the constraint:

```sql
ALTER TABLE users ADD CONSTRAINT users_email_unique UNIQUE (email);
```
````

Cascading fix warning (when the fix itself could introduce a new problem):

````
This handler doesn't validate `userId` before passing it to the query.

Validate and type-cast at the boundary:

```typescript
const userId = parseInt(req.params.userId, 10);
if (Number.isNaN(userId) || userId <= 0) {
  return res.status(400).json({ error: { code: 'INVALID_ID', message: 'userId must be a positive integer' } });
}
```

When implementing this fix, also update the integration tests in
`users.test.ts` to cover the new 400 response path. The existing tests
only send valid IDs, so without a new test case, the validation could
regress silently.
````

Brief positive note when something is genuinely well done:

```
Clean use of the strategy pattern here. Each payment processor
is independently testable and adding a new one doesn't touch
existing code.
```
