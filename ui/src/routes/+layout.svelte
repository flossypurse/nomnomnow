<script>
  import Spinner from "../components/Spinner.svelte";
  import "../app.css";
  let { children } = $props();
</script>

<Spinner />

<nav class="max-w-[800px] mx-auto p-4 bg-slate-100 rounded shadow-md">
  <ul class="flex justify-center gap-4">
    <li>
      <a
        href="/"
        class="text-slate-700 hover:text-slate-800 font-semibold px-3 py-2 rounded hover:bg-slate-200"
      >
        Example App Home
      </a>
    </li>
    <li>
      <a
        href="/order-app"
        class="text-slate-700 hover:text-slate-800 font-semibold px-3 py-2 rounded hover:bg-slate-200"
      >
        Order App
      </a>
    </li>
    <li>
      <a
        href="/restaurant-app"
        class="text-slate-700 hover:text-slate-800 font-semibold px-3 py-2 rounded hover:bg-slate-200"
      >
        Restaurant App
      </a>
    </li>
    <li>
      <a
        href="/driver-app"
        class="text-slate-700 hover:text-slate-800 font-semibold px-3 py-2 rounded hover:bg-slate-200"
      >
        Driver App
      </a>
    </li>
  </ul>
</nav>

<div class="max-w-[800px] mx-auto p-4">
  <img
    src="nomnomnowlogo.png"
    alt="Nom Nom Now logo"
    class="w-32 h-32 rounded-full mx-auto mt-8"
  />
</div>

{@render children()}
