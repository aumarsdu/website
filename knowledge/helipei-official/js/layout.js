document.addEventListener('DOMContentLoaded', () => {
    renderHeader();
    renderFooter();
});

function renderHeader() {
    const header = document.createElement('header');
    header.className = 'navbar';

    const navContainer = document.createElement('div');
    navContainer.className = 'nav-container';

    // Brand/Logo
    const brand = document.createElement('a');
    brand.className = 'nav-brand';
    brand.href = '/index.html';
    brand.textContent = siteConfig.siteName;
    navContainer.appendChild(brand);

    // Navigation Links
    const navLinksContainer = document.createElement('ul');
    navLinksContainer.className = 'nav-links';

    siteConfig.navLinks.forEach(link => {
        const li = document.createElement('li');
        const a = document.createElement('a');
        a.className = 'nav-link';
        a.href = link.url;
        a.textContent = link.name;
        li.appendChild(a);
        navLinksContainer.appendChild(li);
    });

    navContainer.appendChild(navLinksContainer);
    header.appendChild(navContainer);

    document.body.insertBefore(header, document.body.firstChild);
}

function renderFooter() {
    const footer = document.createElement('footer');
    footer.className = 'footer';

    const footerContent = document.createElement('div');
    footerContent.className = 'footer-content';

    // Copyright
    const copyright = document.createElement('p');
    copyright.textContent = siteConfig.footer.copyright;
    footerContent.appendChild(copyright);

    // Social Links (Optional, if present in config)
    if (siteConfig.footer.socialLinks && siteConfig.footer.socialLinks.length > 0) {
        const socialDiv = document.createElement('div');
        socialDiv.className = 'social-links';
        
        siteConfig.footer.socialLinks.forEach(link => {
            const a = document.createElement('a');
            a.href = link.url;
            a.textContent = link.name;
            a.style.marginLeft = '10px';
            a.style.color = 'inherit';
            a.style.textDecoration = 'none';
            socialDiv.appendChild(a);
        });
        footerContent.appendChild(socialDiv);
    }

    footer.appendChild(footerContent);
    document.body.appendChild(footer);
}
