document.addEventListener('DOMContentLoaded', function() {
    const modal = document.getElementById('modal');
    const modalContent = document.getElementById('modal-content');
    const closeBtn = document.querySelector('.close');

    // Handle image card clicks
    document.querySelectorAll('.image-card').forEach(card => {
        card.addEventListener('click', async (event) => {
            // Prevent click handling if the click was on the <a> tag
            if (event.target.closest('a')) {
                return;
            }
            
            event.preventDefault();
            const imageId = card.dataset.id;
            try {
                const response = await fetch(`/reveal_gallery/image/${imageId}`);
                if (!response.ok) {
                    throw new Error(`HTTP error! status: ${response.status}`);
                }
                const html = await response.text();
                modalContent.innerHTML = html;
                modal.style.display = 'block';
            } catch (error) {
                console.error('Error loading image details:', error);
            }
        });
    });

    // Close modal
    closeBtn.addEventListener('click', () => {
        modal.style.display = 'none';
    });

    // Close modal when clicking outside
    window.addEventListener('click', (event) => {
        if (event.target === modal) {
            modal.style.display = 'none';
        }
    });
});
