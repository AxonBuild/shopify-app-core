1. Conversational Product Finder
    - embed description
    - embed picture as well
    - incoming query classifier:
    {
        color: "red" | null,
        size: "L" | null,
        price: ""
    }
2. Purchase-history-aware recommendations
    - based on purachase history, prompt the user
3. AI Support and Policy Agent
    - FAQ 
    - return policy
    - Order status retrieval from Shopify
    - We can provide textbox / file upload / webpage url upload
4. Post-purchase features.
    - Recurring purchase. if selling shampoo, you can contact again after 1 month. 
    - Delivery + feedback + review automation
5. Multimodal Commerce (Voice + Image Search)
    - user can uplaod vn + image (CLIP embeddings)
    - we can find best matches based on that
6. CRM integration
    - using google sheets as a CRM
    - can label leads as first-time, returning, etc.
    - can add notes to leads
    - can add tags to leads
    - can add custom fields to leads

For embeddings, let's use Meilisearch.
- Embeddings + full-text search 