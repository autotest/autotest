package autotest.afe;

import autotest.common.JsonRpcCallback;
import autotest.common.JsonRpcProxy;
import autotest.common.StaticDataRepository;
import autotest.common.Utils;
import autotest.common.StaticDataRepository.FinishedCallback;
import autotest.common.ui.RadioChooser;
import autotest.common.ui.TabView;

import com.google.gwt.json.client.JSONObject;
import com.google.gwt.json.client.JSONString;
import com.google.gwt.json.client.JSONValue;
import com.google.gwt.user.client.ui.Button;
import com.google.gwt.user.client.ui.ClickListener;
import com.google.gwt.user.client.ui.FlexTable;
import com.google.gwt.user.client.ui.HTMLTable;
import com.google.gwt.user.client.ui.Panel;
import com.google.gwt.user.client.ui.RootPanel;
import com.google.gwt.user.client.ui.VerticalPanel;
import com.google.gwt.user.client.ui.Widget;

public class UserPreferencesView extends TabView implements ClickListener {
    private static final StaticDataRepository staticData = StaticDataRepository.getRepository();
    private static final JsonRpcProxy proxy = JsonRpcProxy.getProxy();
    
    public static interface UserPreferencesListener {
        public void onPreferencesChanged();
    }
    
    private JSONObject user;
    private UserPreferencesListener listener;
    
    private RadioChooser rebootBefore = new RadioChooser();
    private RadioChooser rebootAfter = new RadioChooser();
    private Button saveButton = new Button("Save preferences");
    private HTMLTable preferencesTable = new FlexTable();

    public UserPreferencesView(UserPreferencesListener listener) {
        this.listener = listener;
    }

    @Override
    public String getElementId() {
        return "user_preferences";
    }

    @Override
    public void initialize() {
        Panel container = new VerticalPanel();
        AfeUtils.populateRadioChooser(rebootBefore, "reboot_before");
        AfeUtils.populateRadioChooser(rebootAfter, "reboot_after");

        saveButton.addClickListener(this);

        addOption("Reboot before", rebootBefore);
        addOption("Reboot after", rebootAfter);
        container.add(preferencesTable);
        container.add(saveButton);
        RootPanel.get("user_preferences_table").add(container);
    }

    @Override
    public void refresh() {
        staticData.refresh(new FinishedCallback() {
            public void onFinished() {
                user = staticData.getData("current_user").isObject();
                updateValues();
                if (listener != null) {
                    listener.onPreferencesChanged();
                }
            }
        });
    }

    private void updateValues() {
        rebootBefore.setSelectedChoice(getValue("reboot_before"));
        rebootAfter.setSelectedChoice(getValue("reboot_after"));
    }
    
    private String getValue(String key) {
        return Utils.jsonToString(user.get(key));
    }

    public void onClick(Widget sender) {
        assert sender == saveButton;
        saveValues();
    }

    private void saveValues() {
        JSONObject values = new JSONObject();
        values.put("id", user.get("id"));
        values.put("reboot_before", new JSONString(rebootBefore.getSelectedChoice()));
        values.put("reboot_after", new JSONString(rebootAfter.getSelectedChoice()));
        proxy.rpcCall("modify_user", values, new JsonRpcCallback() {
            @Override
            public void onSuccess(JSONValue result) {
                refresh();
            }
        });
    }

    private void addOption(String name, Widget widget) {
        int row = preferencesTable.getRowCount();
        preferencesTable.setText(row, 0, name);
        preferencesTable.setWidget(row, 1, widget);
    }
}
