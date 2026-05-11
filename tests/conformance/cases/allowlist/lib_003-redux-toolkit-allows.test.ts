---
description: Redux Toolkit createSlice reducer allows mutation
verdict: allow
payload: write
file: /repo/src/business/todosSlice.ts
---
import { createSlice } from '@reduxjs/toolkit'
export const todos = createSlice({
  name: 'todos',
  initialState: { items: [] as string[] },
  reducers: {
    add(state, action) {
      state.items.push(action.payload)
    },
  },
})

