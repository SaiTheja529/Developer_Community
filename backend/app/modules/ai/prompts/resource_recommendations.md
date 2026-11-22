---
version: 1
---
Task: recommend an ordered learning path of 3 to 8 resources for the topic described by the user.

- Prefer resources from <hub_resources> (already in the {APP_NAME} Knowledge Hub). Reference them by
  setting hub_resource_id to their id and url to null.
- Add external resources only when the hub does not cover something important. For external resources set
  hub_resource_id to null and url to the exact URL. Prefer official documentation domains.
  Every external URL will be checked automatically; unreachable ones are removed.
- Never invent URLs you are not confident exist.
- resource_type must be one of: {RESOURCE_TYPES}. level must be one of: beginner, intermediate, advanced.
- category must be one of: {CATEGORIES}.
- learning_path_notes: 2 to 4 sentences explaining how to work through the list.
