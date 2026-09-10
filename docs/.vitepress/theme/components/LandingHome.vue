<script setup lang="ts">
import { withBase } from "vitepress";
</script>

<template>
  <main class="shadow-home">
    <section class="intro">
      <div>
        <h1>Pick up where<br />you left off.</h1>
        <p class="lead">
          Keep the plan, who owns the work, and the next step on your computer.
          Open a new coding session and continue.
        </p>
        <a class="action" href="#try-it">Run the local demo</a>
      </div>
      <img
        class="mark"
        :src="withBase('/shadow-icon.png')"
        alt="A person with their shadow cast beside them"
      />
    </section>
    <figure>
      <video
        controls
        preload="metadata"
        :poster="withBase('/shadow-demo.png')"
        aria-label="Shadow failed-check and handoff demo"
      >
        <source :src="withBase('/shadow-demo.mp4')" type="video/mp4" />
        <a :href="withBase('/shadow-demo.mp4')">Watch the demo</a>
      </video>
      <figcaption>
        A real CLI run in a scratch repository: reject a failing check, accept
        the committed fix, then find the next task. No model calls.
      </figcaption>
    </figure>
    <section class="try" id="try-it">
      <div>
        <h2>A small task.<br />The complete loop.</h2>
        <p>
          The example uses a failing greeting test. It creates its own
          repository and board, then removes them when it finishes.
        </p>
        <p>Python 3.10+, Git, and Bash. macOS or Linux.</p>
      </div>
      <div>
        <pre>
git clone https://github.com/firstbitelabsllc/shadow.git
cd shadow
python3 examples/demo.py</pre
        >
        <a :href="withBase('/guide/quickstart')"
          >Use Shadow with your project ↗</a
        >
      </div>
    </section>
    <section class="explain">
      <h2>The work has a place to live.</h2>
      <p>
        The local board records priorities and ownership. Each plan records
        tasks and evidence. Your next coding session reads the same files and
        sees where to continue.
      </p>
      <p>
        You choose the checks. Shadow reruns a task's command against committed
        source before accepting it; a weak check still needs your judgment.
      </p>
    </section>
    <footer>
      <a :href="withBase('/reference/commands')">Command reference</a
      ><span
        ><a href="https://github.com/firstbitelabsllc/shadow/blob/main/LICENSE"
          >MIT license</a
        >
        ·
        <a href="https://github.com/firstbitelabsllc/shadow/issues"
          >Report a problem</a
        ></span
      >
    </footer>
  </main>
</template>

<style scoped>
.shadow-home {
  max-width: 1160px;
  padding: 32px 48px 56px;
  margin: auto;
  font-size: 18px;
  line-height: 1.65;
}
.intro {
  display: grid;
  grid-template-columns: 1.65fr 1fr;
  gap: 24px;
  align-items: center;
  padding: 32px 0 48px;
}
h1 {
  font-size: clamp(52px, 6.4vw, 80px);
  font-weight: 500;
  line-height: 1.06;
  letter-spacing: -0.04em;
  text-wrap: balance;
  margin: 0 0 24px;
}
.lead {
  font-size: 21px;
  color: #56634f;
  max-width: 50ch;
  margin: 0 0 28px;
}
.mark {
  width: 100%;
  max-width: 340px;
}
.action {
  display: inline-block;
  background: #27372c;
  color: #f4f2eb;
  border-radius: 5px;
  padding: 12px 24px;
  text-decoration: none;
  font-size: 16px;
}
.action:hover {
  background: #40543a;
  color: #f4f2eb;
}
a {
  text-decoration: underline;
  text-underline-offset: 5px;
}
a:hover {
  color: #40543a;
}
figure {
  margin: 0;
}
video {
  display: block;
  width: 100%;
  border: 1px solid #c6cec1;
  border-radius: 8px;
}
figcaption {
  font-size: 14px;
  color: #56634f;
  margin-top: 12px;
}
.try {
  display: grid;
  grid-template-columns: 1fr 1.15fr;
  gap: 48px;
  margin-top: 64px;
  border-top: 1px solid #c6cec1;
  padding-top: 32px;
}
h2 {
  font-size: 32px;
  line-height: 1.2;
  font-weight: 500;
  letter-spacing: -0.03em;
  margin: 0 0 20px;
}
.try p {
  color: #56634f;
  max-width: 44ch;
  margin: 0 0 20px;
}
pre {
  font: 14px/1.9 monospace;
  white-space: pre-wrap;
  overflow-wrap: anywhere;
  margin: 0 0 24px;
}
.explain {
  max-width: 72ch;
  margin-top: 48px;
}
.explain p {
  color: #56634f;
  margin: 0 0 16px;
}
footer {
  display: flex;
  justify-content: space-between;
  gap: 24px;
  margin-top: 56px;
  font-size: 14px;
  color: #56634f;
}
@media (max-width: 650px) {
  .shadow-home {
    padding: 24px 24px 40px;
  }
  .intro {
    padding-top: 8px;
    grid-template-columns: 1fr;
  }
  .mark {
    grid-row: 1;
    width: 90px;
  }
  .lead {
    font-size: 19px;
  }
  .try {
    grid-template-columns: 1fr;
    gap: 16px;
    margin-top: 40px;
  }
  footer {
    flex-direction: column;
    gap: 12px;
  }
}
</style>
