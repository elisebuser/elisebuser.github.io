fetch("data/blog.json")
    .then(response => response.json())
    .then(posts => {
        const blogContent = document.getElementById("blogContent");

        posts.forEach(post => {
            const card = document.createElement("a");

            card.href = `blog/post.html?post=${post.slug}`;
            card.className = "blogCard";

            card.innerHTML = `
                <img src="${post.image}" alt="${post.title}">
                <div class="blogCardText">
                    <h2>${post.title}</h2>
                    <p class="blogDate">${post.date}</p>
                    <p>${post.excerpt}</p>
                </div>
            `;

            blogContent.appendChild(card);
        });
    })
    .catch(error => {
        console.error("Error loading blog posts:", error);
    });
