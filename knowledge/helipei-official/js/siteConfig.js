const siteConfig = {
  siteName: "Helibei Official",
  navLinks: [
    { name: "Home", url: "/index.html" },
    { name: "Workshops", url: "/workshops.html" },
    { name: "About", url: "/about.html" },
    { name: "Resources", url: "/resources.html" }
  ],
  workshops: [
    { 
      title: "Summer School Application", 
      url: "#",
      description: "Get comprehensive guidance on applying to top summer schools worldwide.",
      image: "https://placehold.co/600x400?text=Summer+School"
    },
    { 
      title: "Summer Research", 
      url: "#",
      description: "Join intensive summer research programs to boost your academic profile.",
      image: "https://placehold.co/600x400?text=Summer+Research"
    },
    { 
      title: "Research Project", 
      url: "#",
      description: "Engage in cutting-edge research projects mentored by expert faculty.",
      image: "https://placehold.co/600x400?text=Research+Project"
    },
    { 
      title: "Study Abroad Enhancement", 
      url: "#",
      description: "Enhance your study abroad experience with cultural and academic preparation.",
      image: "https://placehold.co/600x400?text=Study+Abroad"
    }
  ],
  about: {
    title: "About Helibei",
    description: "Helibei Official is dedicated to providing students with the best opportunities for academic and personal growth through summer schools, research programs, and study abroad experiences.",
    team: [
      { name: "Alice Johnson", role: "Founder & CEO", bio: "Former admissions officer with 10+ years of experience in higher education." },
      { name: "Bob Smith", role: "Head of Research", bio: "Ph.D. in Physics, passionate about mentoring students in research methodology." },
      { name: "Carol White", role: "Student Advisor", bio: "Expert in study abroad programs and cultural exchange." }
    ]
  },
  resources: [
    { title: "Guide to Summer Schools", url: "#", type: "Guide" },
    { title: "Research Proposal Template", url: "#", type: "Template" },
    { title: "Top 10 Study Abroad Destinations", url: "#", type: "Article" },
    { title: "Scholarship Application Checklist", url: "#", type: "Checklist" }
  ],
  hero: {
    title: "Your Path to Academic Excellence",
    subtitle: "Expert guidance for summer schools, research projects, and study abroad.",
    cta: { text: "Explore Workshops", url: "/workshops.html" }
  },
  features: [
    { title: "Expert Mentors", description: "Learn from top industry professionals and academics." },
    { title: "Proven Curriculum", description: "Follow a structured path designed for success." },
    { title: "Global Network", description: "Connect with peers and mentors from around the world." }
  ],
  footer: {
    copyright: "© 2024 Helibei Official. All rights reserved.",
    socialLinks: [
      { name: "Twitter", url: "#" },
      { name: "LinkedIn", url: "#" },
      { name: "GitHub", url: "#" }
    ]
  }
};

console.log("Site Config Loaded:", siteConfig);
