<script setup lang="ts">
const name = ref('')
const saved = ref<{ id: string; name: string } | null>(null)

async function save() {
  saved.value = await $fetch('/api/items', { method: 'POST', body: { name: name.value } })
}
</script>

<template>
  <form @submit.prevent="save">
    <input v-model="name" placeholder="Item name">
    <button type="submit">Save</button>
    <p v-if="saved">Saved {{ saved.name }}</p>
  </form>
</template>
