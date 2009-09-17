package autotest.common.ui;

import com.google.gwt.user.client.ui.Composite;
import com.google.gwt.user.client.ui.HorizontalPanel;
import com.google.gwt.user.client.ui.Panel;
import com.google.gwt.user.client.ui.RadioButton;

import java.util.ArrayList;
import java.util.List;

public class RadioChooser extends Composite {
    private static int groupNameCounter = 0;
    
    private List<RadioButton> radioButtons = new ArrayList<RadioButton>();
    private RadioButton defaultButton;
    private Panel container = new HorizontalPanel();
    private String groupName = getFreshGroupName();
    
    public RadioChooser() {
        initWidget(container);
        setStyleName("radio-chooser");
    }
    
    private static String getFreshGroupName() {
        groupNameCounter++;
        return "group" + Integer.toString(groupNameCounter);
    }
    
    public void addChoice(String choice) {
        RadioButton button = new RadioButton(groupName, choice);
        if (radioButtons.isEmpty()) {
            // first button in this group
            defaultButton = button;
            button.setValue(true);
        }
        radioButtons.add(button);
        container.add(button);
    }
    
    public String getSelectedChoice() {
        for (RadioButton button : radioButtons) {
            if (button.getValue()) {
                return button.getText();
            }
        }
        throw new RuntimeException("No radio button selected");
    }
    
    public void reset() {
        if (defaultButton != null) {
            defaultButton.setValue(true);
        }
    }

    public void setDefaultChoice(String defaultChoice) {
        defaultButton = findButtonForChoice(defaultChoice);
    }

    public void setSelectedChoice(String choice) {
        findButtonForChoice(choice).setValue(true);
    }
    
    private RadioButton findButtonForChoice(String choice) {
        for (RadioButton button : radioButtons) {
            if (button.getText().equals(choice)) {
                return button;
            }
        }
        throw new RuntimeException("No such choice found: " + choice);
    }
}
