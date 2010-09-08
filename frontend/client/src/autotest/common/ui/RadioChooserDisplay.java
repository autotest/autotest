package autotest.common.ui;

import autotest.afe.IRadioButton;
import autotest.afe.IRadioButton.RadioButtonImpl;

import com.google.gwt.user.client.ui.Composite;
import com.google.gwt.user.client.ui.HorizontalPanel;
import com.google.gwt.user.client.ui.Panel;

public class RadioChooserDisplay extends Composite implements RadioChooser.Display {
    private Panel container = new HorizontalPanel();

    public RadioChooserDisplay() {
        initWidget(container);
        setStyleName("radio-chooser");
    }

    public IRadioButton generateRadioButton(String groupName, String choice) {
        RadioButtonImpl radioButton = new RadioButtonImpl(groupName, choice);
        container.add(radioButton);
        return radioButton;
    }
}
