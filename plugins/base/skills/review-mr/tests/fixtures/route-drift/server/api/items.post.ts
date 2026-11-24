export default defineEventHandler(async (event) => {
  const body = await readBody<{ name?: string; quantity?: number }>(event)
  if (!body.name || body.quantity === undefined) {
    throw createError({ statusCode: 400, statusMessage: 'name and quantity are required' })
  }
  return { id: crypto.randomUUID(), name: body.name, quantity: body.quantity }
})
