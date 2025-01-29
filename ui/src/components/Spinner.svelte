<script>
  import { isLoading } from "../stores/loading";
</script>

{#if $isLoading}
  <div
    class="fixed inset-0 flex items-center justify-center bg-black bg-opacity-50"
  >
    <div
      class="w-16 h-16 border-4 border-blue-500 border-t-transparent rounded-full animate-spin"
    ></div>
  </div>
{/if}

<style>
  /* Optional styles if needed */
</style>
