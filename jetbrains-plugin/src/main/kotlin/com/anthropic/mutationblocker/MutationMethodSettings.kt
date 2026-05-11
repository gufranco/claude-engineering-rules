package com.anthropic.mutationblocker

import com.intellij.openapi.application.ApplicationManager
import com.intellij.openapi.components.PersistentStateComponent
import com.intellij.openapi.components.Service
import com.intellij.openapi.components.State
import com.intellij.openapi.components.Storage
import com.intellij.util.xmlb.XmlSerializerUtil

data class SettingsState(
    var hookPath: String = "",
)

@Service(Service.Level.APP)
@State(name = "MutationMethodBlockerSettings", storages = [Storage("mutation-method-blocker.xml")])
class MutationMethodSettings : PersistentStateComponent<SettingsState> {

    private val internalState = SettingsState()

    override fun getState(): SettingsState = internalState

    override fun loadState(state: SettingsState) {
        XmlSerializerUtil.copyBean(state, internalState)
    }

    fun updateHookPath(path: String) {
        loadState(SettingsState(hookPath = path))
    }

    companion object {
        val instance: MutationMethodSettings
            get() = ApplicationManager.getApplication().getService(MutationMethodSettings::class.java)
    }
}
