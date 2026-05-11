package com.anthropic.mutationblocker

import com.intellij.openapi.options.Configurable
import com.intellij.openapi.options.ConfigurationException
import com.intellij.openapi.ui.TextFieldWithBrowseButton
import com.intellij.openapi.fileChooser.FileChooserDescriptorFactory
import com.intellij.ui.components.JBLabel
import com.intellij.util.ui.FormBuilder
import javax.swing.JComponent
import javax.swing.JPanel

class MutationMethodConfigurable : Configurable {
    private val hookPathField = TextFieldWithBrowseButton().also {
        it.addBrowseFolderListener(
            "Mutation Method Blocker Hook",
            "Path to the Python hook script",
            null,
            FileChooserDescriptorFactory.createSingleFileDescriptor("py"),
        )
    }

    private val panel: JPanel = FormBuilder.createFormBuilder()
        .addLabeledComponent(JBLabel("Hook path:"), hookPathField, 1, false)
        .addComponentFillVertically(JPanel(), 0)
        .panel

    override fun getDisplayName(): String = "Mutation Method Blocker"

    override fun createComponent(): JComponent = panel

    override fun isModified(): Boolean {
        val stored = MutationMethodSettings.instance.state.hookPath
        return hookPathField.text != stored
    }

    @Throws(ConfigurationException::class)
    override fun apply() {
        MutationMethodSettings.instance.updateHookPath(hookPathField.text)
    }

    override fun reset() {
        hookPathField.text = MutationMethodSettings.instance.state.hookPath
    }
}
